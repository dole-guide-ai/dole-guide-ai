"""검색 청크 + 규칙 카드 → 검색 색인(knowledge_chunks). 수집 배치의 마지막 단계입니다.

바뀐 글만 다시 임베딩하므로 여러 번 돌려도 됩니다. 지식 청크 파일이 없으면(저장소에 올리지 않음)
규칙 카드만 넣고, 색인에 있던 청크는 그대로 둡니다.

uv run python -m scripts.ingest.index
"""

import json

from app.core.db import SessionLocal
from app.schemas.knowledge import KnowledgeKind
from app.services import knowledge as knowledge_service
from app.services.knowledge import RULE_ID_PREFIX, SourceDoc
from scripts.ingest import paths

CHUNK_FILES = (paths.FAQ_CHUNKS, paths.POLICY_CATALOG_CHUNKS, paths.POLICY_CONTENT_CHUNKS)
# 원본 청크의 metadata 중 색인에 남길 칸(출처 표시·고용 형태 거르기용)
META_KEYS = ("source", "source_url", "title", "policy_name", "published_at", "last_modified",
             "employment_type")  # fmt: skip


def chunk_doc(row: dict) -> SourceDoc:
    meta = row["metadata"]
    kind = KnowledgeKind.FAQ if row["chunk_scope"] == "faq" else KnowledgeKind.POLICY
    return SourceDoc(
        chunk_id=row["chunk_id"],
        kind=kind,
        title=meta.get("title") or meta.get("policy_name") or row["chunk_id"],
        text=row["content"],
        meta={
            "scope": row["chunk_scope"],
            "chunk_type": row["chunk_type"],
            "policy_id": row["policy_id"],
            "faq_id": row["faq_id"],
            **{k: meta[k] for k in META_KEYS if meta.get(k) is not None},
        },
    )


def chunk_documents() -> list[SourceDoc] | None:
    if not all(f.exists() for f in CHUNK_FILES):
        return None
    docs = []
    for path in CHUNK_FILES:
        with path.open(encoding="utf-8") as f:
            docs += [chunk_doc(json.loads(line)) for line in f if line.strip()]
    return docs


def main() -> None:
    docs = knowledge_service.rule_card_documents()
    chunks = chunk_documents()
    with SessionLocal() as db:
        if chunks is None:
            print("지식 청크 파일이 없어 규칙 카드만 넣습니다.")
            ids = knowledge_service.indexed_ids(db)
            kept = [c for c in ids if not c.startswith(RULE_ID_PREFIX)]
            result = knowledge_service.sync_index(db, docs, keep_extra=kept)
        else:
            result = knowledge_service.sync_index(db, docs + chunks)
    print(f"임베딩 {result.embedded} · 그대로 {result.unchanged} · 삭제 {result.deleted}")


if __name__ == "__main__":
    main()
