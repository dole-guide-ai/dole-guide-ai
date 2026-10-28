"""시연 계정 seed 파일을 읽어 personas 테이블에 넣는 서비스입니다.

seed는 backend/data/seeds/personas.json에 있고, 날짜는 입장일 기준 상대값(예: -21은 입장 21일
전)입니다.
계정을 만들 때 at()으로 상대 날짜를 실제 날짜로 바꿉니다. 그래서 언제 시연해도 같은 상황이
나옵니다. 경력의 퇴사월처럼 이직일에 맞춰야 하는 글자는 `{sep:%Y-%m}`으로 쓰고 resolve_seed()가
채웁니다.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import accounts as repo

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seeds" / "personas.json"
# seed 글자에서 이직일 자리를 나타내는 이름 (예: "2012-03 ~ {sep:%Y.%m}")
SEPARATION_FIELD = "{sep"


def read_seed_file(path: Path = SEED_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["personas"]


def load_personas(db: Session, path: Path = SEED_PATH) -> int:
    personas = read_seed_file(path)
    for persona in personas:
        repo.upsert_persona(
            db,
            persona["persona_id"],
            persona["display"],
            persona,
            persona.get("sort_order", 0),
        )
    db.commit()
    return len(personas)


def at(anchor: date, offset: int | None) -> date | None:
    return None if offset is None else anchor + timedelta(days=offset)


def resolve_seed(seed: dict[str, Any], anchor: date) -> dict[str, Any]:
    """seed 글자 속 `{sep:%Y-%m}`처럼 쓴 이직일 자리를 이 계정의 이직일로 채웁니다.

    이직일이 입장일 기준 상대값이라, 마지막 경력의 퇴사월도 이직일에서 만들어야 언제 입장해도
    두 값이 같은 달이 됩니다(경력 끝 ≠ 이직월이면 이력서 검사가 다시 묻습니다).
    """
    separation = at(anchor, seed["procedure"]["separation_offset"])

    def fill(value: Any) -> Any:
        if isinstance(value, str):
            return value.format(sep=separation) if SEPARATION_FIELD in value else value
        if isinstance(value, list):
            return [fill(v) for v in value]
        if isinstance(value, dict):
            return {k: fill(v) for k, v in value.items()}
        return value

    return fill(seed)
