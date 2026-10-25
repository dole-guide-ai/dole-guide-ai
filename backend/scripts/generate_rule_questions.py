"""규칙 카드마다 사용자가 할 법한 질문을 만들어 data/rules/rule_questions.csv에 씁니다(doc2query).

카드는 "임금체불 발생"처럼 규칙의 말로 적혀 있고 사용자는 "월급이 안 나와서 그만뒀는데"처럼
묻습니다. 질문을 카드의 검색할 글에 덧붙여 그 차이를 줄입니다. 검색에만 쓰고 모델이 읽는 카드
내용은 바꾸지 않습니다. 카드 글의 해시를 같이 적어, 규칙표가 바뀐 카드만 다시 만듭니다.

평가 질문(evals/retrieval)은 모델에 보여 주지 않습니다(평가 점수가 부풀지 않게).
실행: backend/에서 `uv run python scripts/generate_rule_questions.py` → 그다음 색인 다시 채우기
"""

import csv
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import gateway  # noqa: E402
from app.agent.prompts import load_prompt  # noqa: E402
from app.rules.rule_cards import (  # noqa: E402
    QUESTIONS_FILE,
    RuleCard,
    card_text_hash,
    load_card_questions,
    load_cards,
)

PROMPT = "retrieval/card_questions"
QUESTIONS_PER_CARD = 3
WORKERS = 8


class CardQuestions(BaseModel):
    questions: list[str] = Field(min_length=1, max_length=QUESTIONS_PER_CARD)


def generate(card: RuleCard) -> list[str]:
    model = gateway.get_chat_model("extract").with_structured_output(CardQuestions)
    card_lines = "\n".join(f"{k}: {v}" for k, v in card.for_model().items() if k != "id")
    result = model.invoke([SystemMessage(load_prompt(PROMPT)), HumanMessage(card_lines)])
    return [q.strip() for q in result.questions if q.strip()][:QUESTIONS_PER_CARD]


def main() -> None:
    cards = load_cards()
    existing = load_card_questions()
    todo = [c for c in cards if existing.get(c.rule_id, ("", ()))[0] != card_text_hash(c)]
    with ThreadPoolExecutor(WORKERS) as pool:
        fresh = dict(zip((c.rule_id for c in todo), pool.map(generate, todo), strict=True))
    with QUESTIONS_FILE.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["rule_id", "card_hash", "question"])
        for card in cards:
            questions = fresh.get(card.rule_id) or existing[card.rule_id][1]
            writer.writerows([card.rule_id, card_text_hash(card), q] for q in questions)
    print(f"새로 만듦 {len(todo)} · 그대로 {len(cards) - len(todo)}")


if __name__ == "__main__":
    main()
