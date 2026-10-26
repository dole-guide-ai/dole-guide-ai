"""정책·FAQ 조각마다 그 조각이 답이 될 질문을 만들어 검색 평가 질문셋으로 씁니다.

결과는 evals/retrieval/guide_queries.jsonl("정책·FAQ 생성" 세트, evals/retrieval/run.py가 읽음)이고
저장소에 올립니다. 팀이 같은 질문으로 점수를 견주게 하려는 것으로, 크롤링 원문이 아니라 생성한
질문과 조각 ID만 담깁니다. 질문은 그 조각 하나를 정답으로 둡니다.

- FAQ: 모든 조각(질의를 그대로 쓰지 않고 사용자 말투로 바꿔 씀)
- 정책 본문: 글이 충분한 조각 중 정책별로 고르게 SAMPLE_POLICY_SECTIONS개
이미 만든 질문은 다시 만들지 않습니다.
실행: backend/에서 `uv run python scripts/generate_guide_questions.py`
"""

import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import gateway  # noqa: E402
from app.agent.prompts import load_prompt  # noqa: E402
from scripts.ingest import paths  # noqa: E402

PROMPT = "retrieval/guide_questions"
OUT = Path(__file__).resolve().parents[1] / "evals" / "retrieval" / "guide_queries.jsonl"
FAQ_FILE = paths.FAQ_CHUNKS
POLICY_FILE = paths.POLICY_CONTENT_CHUNKS
SAMPLE_POLICY_SECTIONS = 150
MIN_POLICY_CHARS = 80  # 이보다 짧은 조각(목차·양식 이름)은 물을 내용이 적음
SEED = 226
WORKERS = 8
QUESTION_MAX_CHARS = 60


class GuideQuestion(BaseModel):
    question: str = Field(max_length=QUESTION_MAX_CHARS)


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def pick_chunks() -> list[dict]:
    """FAQ 전부 + 정책 본문 조각을 정책이 고르게 섞이도록 뽑습니다(시드 고정)."""
    policy = [r for r in _rows(POLICY_FILE) if len(r["content"]) >= MIN_POLICY_CHARS]
    random.Random(SEED).shuffle(policy)
    by_policy: dict[str, list[dict]] = {}
    for row in policy:
        by_policy.setdefault(row["policy_id"], []).append(row)
    picked: list[dict] = []
    while len(picked) < SAMPLE_POLICY_SECTIONS and any(by_policy.values()):
        for rows in by_policy.values():
            if rows and len(picked) < SAMPLE_POLICY_SECTIONS:
                picked.append(rows.pop())
    return _rows(FAQ_FILE) + picked


def generate(chunk: dict) -> str:
    model = gateway.get_chat_model("extract").with_structured_output(GuideQuestion)
    result = model.invoke([SystemMessage(load_prompt(PROMPT)), HumanMessage(chunk["content"])])
    return result.question.strip()


def main() -> None:
    done = {r["positives"][0]: r for r in _rows(OUT)} if OUT.exists() else {}
    todo = [c for c in pick_chunks() if c["chunk_id"] not in done]
    with ThreadPoolExecutor(WORKERS) as pool:
        questions = list(pool.map(generate, todo))
    for chunk, question in zip(todo, questions, strict=True):
        if question:
            scope = "faq" if chunk["chunk_scope"] == "faq" else "policy"
            done[chunk["chunk_id"]] = {
                "qid": f"{scope}-{chunk['chunk_id']}",
                "question": question,
                "positives": [chunk["chunk_id"]],
                "scope": scope,
            }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + "\n" for r in done.values())
    print(f"새로 만듦 {len(todo)} · 전체 {len(done)} → {OUT}")


if __name__ == "__main__":
    main()
