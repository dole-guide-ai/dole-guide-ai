"""RAG 생성 품질 평가 (RAGAS, 노션 「RAG 설계 (복사본)」 6 · 7.7).

rag_set.jsonl의 test 질문 중 답 있는 질문에 대해 검색 → 답 생성 → RAGAS 지표를 잽니다.
판정 모델은 gateway의 judge 역할입니다(모델끼리 비교할 때는 판정 모델을 고정).
선택 의존성이 필요합니다: uv sync --extra rageval

uv run python -m evals.rag.ragas_eval [--limit 30]
결과는 evals/reports/ragas-*.md (노션 7.7 '평가 연결' 표에 옮김)
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.agent import gateway  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.services import knowledge as knowledge_service  # noqa: E402
from evals.rag.test_rag import REPORTS, _items  # noqa: E402

RAG_DIR = Path(__file__).parent
METRIC_NAMES = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def _answer(question: str, contexts: list[str]) -> str:
    prompt = (RAG_DIR / "prompts" / "answer.md").read_text(encoding="utf-8")
    numbered = "\n\n".join(f"[{i}] {c}" for i, c in enumerate(contexts, start=1))
    filled = prompt.replace("{question}", question).replace("{contexts}", numbered)
    return str(gateway.get_chat_model("agent").invoke(filled).content).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGAS 평가")
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import answer_relevancy, context_precision, context_recall, faithfulness
    except ImportError:
        sys.exit("RAGAS가 없어요. backend에서 uv sync --extra rageval 후 다시 실행해 주세요.")

    rows = {"question": [], "contexts": [], "answer": [], "ground_truth": []}
    items = [i for i in _items("test") if i["gold_chunk_ids"]][: args.limit]
    with SessionLocal() as db:
        for item in items:
            found = knowledge_service.search(db, item["question"])
            contexts = [c["text"] for c in found]
            gold = knowledge_service.repo.chunks_by_id(db, item["gold_chunk_ids"])
            rows["question"].append(item["question"])
            rows["contexts"].append(contexts)
            rows["answer"].append(_answer(item["question"], contexts))
            rows["ground_truth"].append("\n".join(c.content for c in gold.values()))
    result = evaluate(
        Dataset.from_dict(rows),
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        llm=LangchainLLMWrapper(gateway.get_chat_model("judge")),
        embeddings=LangchainEmbeddingsWrapper(gateway.get_embeddings()),
    )
    scores = {name: float(result[name]) for name in METRIC_NAMES}
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"ragas-{datetime.now():%Y%m%d-%H%M%S}.md"
    table = "\n".join(f"| {k} | {v:.3f} |" for k, v in scores.items())
    path.write_text(
        f"# RAGAS ({len(items)}문항)\n\n| 지표 | 값 |\n| --- | --- |\n{table}\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({"report": str(path), **scores}, ensure_ascii=False))


if __name__ == "__main__":
    main()
