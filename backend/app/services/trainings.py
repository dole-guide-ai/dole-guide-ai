"""훈련과정·취업역량 프로그램 조회 (F-29, 설계 3.9).

조건을 비우면 이력서의 희망 직종 이름을 과정명 키워드로 씁니다. 고용24 채용 직종코드와 NCS는 다른
체계라 코드를 바꿔 넣지 않습니다(데이터 설계 8.2). 실시간 조회가 안 되면 스냅샷(data/snapshots)으로
대체하고 source=snapshot을 붙이며, 스냅샷도 없으면 503 EXTERNAL_UNAVAILABLE입니다. 결과는 저장하지
않습니다.
"""

import json
import uuid
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ExternalUnavailableError
from app.repositories import accounts as repo
from app.schemas.trainings import ExternalSource, Program, ProgramList, Training, TrainingList
from app.services import work24_api
from app.services.accounts import AccountContext

SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


@lru_cache(maxsize=2)
def _snapshot(name: str) -> dict[str, Any] | None:
    path = SNAPSHOT_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def desired_occupation(db: Session, user_id: uuid.UUID) -> str | None:
    """이력서 희망 직종 중 이름이 있는 첫 번째."""
    resume = repo.get_resume(db, user_id)
    occupations = ((resume.data if resume else {}).get("job_preferences") or {}).get(
        "desired_occupations"
    ) or []
    names = (((o.get("occupation") or {}).get("value") or {}).get("name") for o in occupations)
    return next((n for n in names if n), None)


def _matches(row: dict[str, Any], keyword: str | None, region: str | None) -> bool:
    words = [row.get("title", ""), *row.get("keywords", [])]
    by_keyword = not keyword or any(keyword in w or w in keyword for w in words if w)
    return by_keyword and (not region or region in (row.get("region") or ""))


def search_trainings(
    keyword: str | None, region: str | None, today: date, now: datetime, page: int = 1
) -> TrainingList:
    """키워드로 훈련과정을 찾습니다. 추천(F-30)과 대화 도구도 이 함수를 씁니다."""
    live = work24_api.fetch_trainings(keyword, today, page)
    if live is not None:
        items = [t for t in live if not region or region in (t.region or "")]
        return TrainingList(
            items=items, total=len(items), source=ExternalSource.LIVE, fetched_at=now
        )
    snapshot = _snapshot("trainings")
    if snapshot is None:
        raise ExternalUnavailableError()
    rows = [r for r in snapshot["items"] if _matches(r, keyword, region)]
    items = [Training.model_validate({k: v for k, v in r.items() if k != "keywords"}) for r in rows]
    return TrainingList(
        items=items,
        total=len(items),
        source=ExternalSource.SNAPSHOT,
        fetched_at=datetime.fromisoformat(snapshot["fetched_at"]),
    )


def search_programs(start: date | None, now: datetime) -> ProgramList:
    live = work24_api.fetch_programs(start)
    if live is not None:
        return ProgramList(items=live, total=len(live), source=ExternalSource.LIVE, fetched_at=now)
    snapshot = _snapshot("programs")
    if snapshot is None:
        raise ExternalUnavailableError()
    items = [Program(id=f"snapshot-{index}", **row) for index, row in enumerate(snapshot["items"])]
    return ProgramList(
        items=items,
        total=len(items),
        source=ExternalSource.SNAPSHOT,
        fetched_at=datetime.fromisoformat(snapshot["fetched_at"]),
    )


def list_trainings(
    db: Session,
    account: AccountContext,
    region: str | None,
    occupation: str | None,
    page: int,
    now: datetime,
) -> TrainingList:
    keyword = occupation or desired_occupation(db, account.user_id)
    return search_trainings(keyword, region, now.date(), now, page)


def list_programs(start: date | None, now: datetime) -> ProgramList:
    return search_programs(start, now)
