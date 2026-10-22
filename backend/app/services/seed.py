"""시연 계정 seed 파일을 읽어 personas 테이블에 넣는 서비스입니다.

seed는 backend/data/seeds/personas.json에 있고, 날짜는 입장일 기준 상대값(예: -21은 입장 21일
전)입니다.
계정을 만들 때 at()으로 상대 날짜를 실제 날짜로 바꿉니다. 그래서 언제 시연해도 같은 상황이
나옵니다.
"""

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.repositories import accounts as repo

SEED_PATH = Path(__file__).resolve().parents[2] / "data" / "seeds" / "personas.json"


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
