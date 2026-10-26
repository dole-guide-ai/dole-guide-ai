"""RAG 평가 질문셋(rag_set.jsonl)을 만듭니다 (노션 「RAG 설계 (복사본)」 7.6).

- ② faq_paraphrase: FAQ 청크의 질문을 중장년 구어체로 바꿈. 정답 = 그 청크
- ③ generated: FAQ가 없는 정책 본문(자격 · 절차 · 지원 내용)에서 질문을 만듦. 정답 = 그 청크
- ⑤ unanswerable: 자료에 없는 질문(unanswerable.json). 정답 없음
- split: 질문 ID 해시로 dev 80% / test 20% (다시 만들어도 같은 쪽)
- reviewed: 사람이 검수하면 true로 바꿉니다. ②·③은 무작위 20%를 검수합니다.

knowledge 스키마에 청크가 적재돼 있어야 합니다(scripts/ingest/load_chunks.py).
LLM은 gateway의 extract 역할을 씁니다.

uv run python -m evals.rag.build_set --paraphrase 150 --generated 50
"""

import argparse
import hashlib
import json
import random
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.agent import gateway  # noqa: E402
from app.agent.input.pii import mask  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.repositories import knowledge as repo  # noqa: E402

RAG_DIR = Path(__file__).parent
OUT = RAG_DIR / "rag_set.jsonl"
UNANSWERABLE = RAG_DIR / "unanswerable.json"
TEST_SHARE = 20  # test 비율(%)
SEED = 20261026
FAQ_TYPES = ("faq_pair", "faq")
GENERATED_SECTIONS = ("eligibility", "procedure", "benefits", "cautions")
QUESTION_LINE = re.compile(r"^질의:\s*(.+)$", re.MULTILINE)


def _prompt(name: str) -> str:
    return (RAG_DIR / "prompts" / f"{name}.md").read_text(encoding="utf-8")


def _split(item_id: str) -> str:
    bucket = int(hashlib.sha256(item_id.encode()).hexdigest(), 16) % 100
    return "test" if bucket < TEST_SHARE else "dev"


def _ask(prompt: str) -> str:
    text = str(gateway.get_chat_model("extract").invoke(prompt).content).strip()
    return mask(text.splitlines()[0] if text else "")[0]


def _faq_question(content: str) -> str | None:
    match = QUESTION_LINE.search(content)
    return match.group(1).strip() if match else None


def build(paraphrase: int, generated: int) -> list[dict[str, Any]]:
    rng = random.Random(SEED)
    with SessionLocal() as db:
        chunks = repo.all_chunks(db)
    faqs = [c for c in chunks if c.chunk_type in FAQ_TYPES and _faq_question(c.content)]
    bodies = [c for c in chunks if c.section_type in GENERATED_SECTIONS]
    items: list[dict[str, Any]] = []
    for chunk in rng.sample(faqs, min(paraphrase, len(faqs))):
        question = _ask(_prompt("paraphrase").replace("{question}", _faq_question(chunk.content)))
        items.append(_item(f"P-{chunk.chunk_id}", question, [chunk.chunk_id], "faq_paraphrase"))
    for chunk in rng.sample(bodies, min(generated, len(bodies))):
        prompt = _prompt("generate").replace("{title}", chunk.title)
        question = _ask(prompt.replace("{content}", chunk.content))
        items.append(_item(f"G-{chunk.chunk_id}", question, [chunk.chunk_id], "generated"))
    unanswerable = json.loads(UNANSWERABLE.read_text(encoding="utf-8"))["questions"]
    for index, question in enumerate(unanswerable, start=1):
        items.append(_item(f"U-{index:03d}", question, [], "unanswerable"))
    return [i for i in items if i["question"]]


def _item(item_id: str, question: str, gold: list[str], kind: str) -> dict[str, Any]:
    return {
        "id": item_id,
        "question": question,
        "gold_chunk_ids": gold,
        "kind": kind,
        "split": _split(item_id),
        "reviewed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="RAG 평가 질문셋 만들기")
    parser.add_argument("--paraphrase", type=int, default=150)
    parser.add_argument("--generated", type=int, default=50)
    args = parser.parse_args()
    items = build(args.paraphrase, args.generated)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    print(json.dumps({"items": len(items), "out": str(OUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
