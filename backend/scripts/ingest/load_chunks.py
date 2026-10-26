"""청크(JSONL)를 RAG 근거 자료 테이블(knowledge 스키마)에 적재합니다.

노션 「RAG 설계 (복사본)」 7.5. chunk.py가 만든 data/knowledge/chunks/*.jsonl을 그대로 씁니다
(다시 청킹하지 않음).

- 멱등: 내용 해시가 바뀐 청크만 고쳐 쓰고, 파일에서 사라진 청크는 지웁니다.
- 임베딩은 없거나 내용이 바뀐 청크만 다시 만듭니다. 모델마다 따로 저장해 비교 실험에도 씁니다.
- 출처 ID는 KB-{source}-{doc_id} (근거 줄 rule_refs).

uv run python -m scripts.ingest.load_chunks                 # 설정의 EMBEDDING_MODEL
uv run python -m scripts.ingest.load_chunks --no-embeddings # BM25용 형태소만
uv run python -m scripts.ingest.load_chunks --model <모델>   # 비교 실험용 다른 모델
"""

import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.agent import gateway  # noqa: E402
from app.core.config import PROVIDERS, get_settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.repositories import knowledge as repo  # noqa: E402
from app.services import knowledge as knowledge_service  # noqa: E402
from scripts.ingest import paths  # noqa: E402

CHUNK_FILES = (paths.POLICY_CATALOG_CHUNKS, paths.POLICY_CONTENT_CHUNKS, paths.FAQ_CHUNKS)
TRUE_TEXT = "true"


def _date(raw: Any) -> date | None:
    try:
        return date.fromisoformat(str(raw)[:10]) if raw else None
    except ValueError:
        return None


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def to_chunk(row: dict[str, Any]) -> repo.KnowledgeChunk:
    meta = row.get("metadata") or {}
    source = meta.get("source", "")
    doc_id = row.get("policy_id") or row.get("faq_id") or row["chunk_id"]
    content = row["content"]
    return repo.KnowledgeChunk(
        chunk_id=row["chunk_id"],
        source_id=f"KB-{source}-{doc_id}",
        source=source,
        doc_id=doc_id,
        chunk_scope=row.get("chunk_scope") or "",
        chunk_type=row.get("chunk_type") or "",
        section_type=row.get("section_type"),
        sequence=int(row.get("sequence") or 0),
        title=(meta.get("title") or meta.get("policy_name") or "")[:300],
        content=content,
        source_url=meta.get("source_url"),
        updated_on=_date(meta.get("last_modified") or meta.get("published_at")),
        priority=meta.get("priority") or "secondary",
        needs_verification=str(meta.get("requires_policy_verification", "")).lower() == TRUE_TEXT,
        content_hash=_hash(content),
        tokens=knowledge_service.tokenize(content),
        metadata_json=meta,
    )


def read_rows(files: tuple[Path, ...] = CHUNK_FILES) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in files:
        if not path.is_file():
            sys.exit(f"청크 파일이 없어요: {path} (data/knowledge는 팀원에게 받아 넣어 주세요)")
        with path.open(encoding="utf-8") as f:
            rows += [json.loads(line) for line in f if line.strip()]
    return rows


def load(model: str | None, embed: bool = True, provider: str | None = None) -> dict[str, int]:
    rows = read_rows()
    chunks = [to_chunk(row) for row in rows]
    with SessionLocal() as db:
        for chunk in chunks:
            repo.upsert_chunk(db, chunk)
        removed = repo.delete_chunks_except(db, {c.chunk_id for c in chunks})
        db.flush()
        embedded = _embed(db, chunks, model, provider) if embed and model else 0
        db.commit()
    knowledge_service.reset_index()
    return {"chunks": len(chunks), "removed": removed, "embedded": embedded}


def _embed(
    db: Any, chunks: list[repo.KnowledgeChunk], model: str, provider: str | None = None
) -> int:
    done = repo.embedding_hashes(db, model)
    todo = [c for c in chunks if done.get(c.chunk_id) != c.content_hash]
    settings = get_settings()
    provider = provider or settings.embedding_provider
    batch = PROVIDERS[provider].embedding_batch_size
    embedder = gateway.get_embeddings(provider, model)
    for start in range(0, len(todo), batch):
        part = todo[start : start + batch]
        vectors = embedder.embed_documents([c.content for c in part])
        for chunk, vector in zip(part, vectors, strict=True):
            repo.upsert_embedding(
                db,
                repo.ChunkEmbedding(
                    chunk_id=chunk.chunk_id,
                    model=model,
                    dim=len(vector),
                    embedding=vector,
                    content_hash=chunk.content_hash,
                ),
            )
        db.flush()
    return len(todo)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", default=None, help="임베딩 모델 (기본: EMBEDDING_MODEL)")
    parser.add_argument("--provider", default=None, help="임베딩 공급자 (기본: EMBEDDING_PROVIDER)")
    parser.add_argument("--no-embeddings", action="store_true", help="형태소만 적재")
    args = parser.parse_args()
    model = args.model or get_settings().embedding_model
    result = load(model, embed=not args.no_embeddings, provider=args.provider)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
