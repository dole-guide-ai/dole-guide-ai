"""RAG 검색 평가 (노션 「RAG 설계 (복사본)」 7.2 · 7.3 · 7.4 · 7.6).

`pnpm eval:rag` — rag_set.jsonl의 test 질문으로 설정마다 검색 지표를 재고 보고서를 씁니다.
리랭커 켬 · 끔을 함께 비교합니다. 임베딩 모델 비교는 --embedding-model로 모델을 바꿔 돌린 보고서를
견줍니다(모델마다 load_chunks.py --model로 먼저 임베딩을 적재). 결과는 노션 7.3 · 7.4 표에 옮깁니다.

- 검색 지표(Recall@5 · MRR@10 · nDCG@10)는 답 있는 질문으로, '찾지 못함' 비율은 답 없는 질문으로
- 지연 시간은 이 컴퓨터 기준이라 Lightsail 실측은 서버에서 다시 잽니다.
"""

import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.services import knowledge as knowledge_service
from evals.rag.metrics import mean, mrr_at_k, ndcg_at_k, recall_at_k

pytestmark = pytest.mark.eval

RAG_DIR = Path(__file__).parent
SET_PATH = RAG_DIR / "rag_set.jsonl"
REPORTS = RAG_DIR.parent / "reports"
RECALL_K, MRR_K, NDCG_K = 5, 10, 10


def _items(split: str) -> list[dict[str, Any]]:
    if not SET_PATH.is_file():
        return []
    rows = [json.loads(line) for line in SET_PATH.read_text(encoding="utf-8").splitlines() if line]
    return [r for r in rows if r["split"] == split]


def evaluate(items: list[dict[str, Any]], use_reranker: bool) -> dict[str, float]:
    recall, mrr, ndcg, latency, refused = [], [], [], [], []
    with SessionLocal() as db:
        knowledge_service.search(db, "실업급여", use_reranker=use_reranker)  # 인덱스 · 모델 준비
        for item in items:
            started = time.perf_counter()
            found = knowledge_service.search(db, item["question"], use_reranker=use_reranker)
            latency.append(time.perf_counter() - started)
            ranked = [c["chunk_id"] for c in found]
            gold = set(item["gold_chunk_ids"])
            if not gold:
                refused.append(1.0 if not ranked else 0.0)
                continue
            recall.append(recall_at_k(ranked, gold, RECALL_K))
            mrr.append(mrr_at_k(ranked, gold, MRR_K))
            ndcg.append(ndcg_at_k(ranked, gold, NDCG_K))
    ordered = sorted(latency)
    return {
        "recall@5": mean(recall),
        "mrr@10": mean(mrr),
        "ndcg@10": mean(ndcg),
        "not_found_rate(unanswerable)": mean(refused),
        "latency_avg_s": mean(latency),
        "latency_p95_s": ordered[int(len(ordered) * 0.95) - 1] if ordered else 0.0,
        "questions": float(len(items)),
    }


def _write_report(rows: dict[str, dict[str, float]], split: str) -> Path:
    REPORTS.mkdir(exist_ok=True)
    settings = get_settings()
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = REPORTS / f"rag-{stamp}.md"
    metrics = list(next(iter(rows.values())))
    lines = [
        f"# RAG 검색 평가 ({split})",
        "",
        f"- 임베딩: {settings.embedding_provider} / {settings.embedding_model or '(없음, BM25만)'}",
        f"- RRF k={settings.rag_rrf_k}, BM25 top {settings.rag_bm25_top_k}, "
        f"벡터 top {settings.rag_vector_top_k}, 결과 {settings.rag_result_top_n}",
        "",
        "| 설정 | " + " | ".join(metrics) + " |",
        "| --- | " + " | ".join("---" for _ in metrics) + " |",
    ]
    for name, values in rows.items():
        lines.append(f"| {name} | " + " | ".join(f"{values[m]:.3f}" for m in metrics) + " |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


@pytest.mark.skipif(
    not _items("test"), reason="rag_set.jsonl이 없어요. build_set.py를 먼저 돌려 주세요."
)
def test_rag_retrieval_report(request) -> None:
    split = request.config.getoption("--rag-split")
    items = _items(split)
    rows = {"리랭커 끔": evaluate(items, use_reranker=False)}
    if request.config.getoption("--rag-reranker"):
        rows["리랭커 켬"] = evaluate(items, use_reranker=True)
    report = _write_report(rows, split)
    print(f"보고서: {report}")
    assert rows["리랭커 끔"]["questions"] > 0
