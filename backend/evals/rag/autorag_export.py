"""AutoRAG 실험용 데이터 내보내기 (노션 「RAG 설계 (복사본)」 6 · 7.2: 오프라인 실험 전용).

서비스에는 AutoRAG을 넣지 않습니다. 여기서 corpus.parquet · qa.parquet(AutoRAG 형식)을 만들고,
AutoRAG은 별도 가상환경에서 autorag.yaml로 돌려 리랭커 · 임베딩 · top-k 조합을 찾습니다.
고른 조합은 설정(RAG_* · RERANKER_*)과 노션 7.3 · 7.4에 옮깁니다. dev 질문만 씁니다.

uv sync --extra rageval
uv run python -m evals.rag.autorag_export
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.core.db import SessionLocal  # noqa: E402
from app.repositories import knowledge as repo  # noqa: E402
from evals.rag.test_rag import _items  # noqa: E402

OUT_DIR = Path(__file__).parent / "autorag_data"


def main() -> None:
    try:
        import pandas as pd
    except ImportError:
        sys.exit("pandas가 없어요. backend에서 uv sync --extra rageval 후 다시 실행해 주세요.")
    with SessionLocal() as db:
        chunks = repo.all_chunks(db)
    corpus = pd.DataFrame(
        {
            "doc_id": [c.chunk_id for c in chunks],
            "contents": [c.content for c in chunks],
            "metadata": [{"source_id": c.source_id, "title": c.title} for c in chunks],
        }
    )
    items = [i for i in _items("dev") if i["gold_chunk_ids"]]
    qa = pd.DataFrame(
        {
            "qid": [i["id"] for i in items],
            "query": [i["question"] for i in items],
            "retrieval_gt": [[i["gold_chunk_ids"]] for i in items],
            "generation_gt": [[""] for _ in items],
        }
    )
    OUT_DIR.mkdir(exist_ok=True)
    corpus.to_parquet(OUT_DIR / "corpus.parquet")
    qa.to_parquet(OUT_DIR / "qa.parquet")
    print(f"corpus {len(corpus)} · qa {len(qa)} → {OUT_DIR}")


if __name__ == "__main__":
    main()
