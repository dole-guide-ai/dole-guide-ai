"""훈련과정·취업역량 프로그램 조회 (F-29, 설계 3.9).

조건을 비우면 이력서의 희망 직종 이름을 과정명 키워드로 씁니다. 고용24 채용 직종코드와 NCS는 다른
체계라 코드를 바꿔 넣지 않습니다(데이터 설계 8.2). 실시간 조회가 안 되면 스냅샷(data/snapshots)으로
대체하고 source=snapshot을 붙이며, 스냅샷도 없으면 503 EXTERNAL_UNAVAILABLE입니다. 결과는 저장하지
않습니다.
"""

import json
import uuid
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ExternalUnavailableError
from app.repositories import accounts as repo
from app.rules import work24_codes
from app.rules.work24_codes import said_name
from app.schemas.trainings import ExternalSource, Program, ProgramList, Training, TrainingList
from app.services import work24_api
from app.services.accounts import AccountContext

DATE_LENGTH = len("2026-01-01")
SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "data" / "snapshots"


@lru_cache(maxsize=2)
def _snapshot(name: str) -> dict[str, Any] | None:
    path = SNAPSHOT_DIR / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def desired_occupation(db: Session, user_id: uuid.UUID) -> str | None:
    """이력서 희망 직종 중 이름이 있는 첫 번째. 검색어라서 고용24 공식 이름보다 사용자가
    말한 이름을 씁니다(예: "총무 및 일반 사무원"이 아니라 "일반 사무")."""
    resume = repo.get_resume(db, user_id)
    occupations = ((resume.data if resume else {}).get("job_preferences") or {}).get(
        "desired_occupations"
    ) or []
    names = (said_name((o.get("occupation") or {}).get("value")) for o in occupations)
    return next((n for n in names if n), None)


def _matches(row: dict[str, Any], keyword: str | None, region: str | None) -> bool:
    words = [row.get("title", ""), *row.get("keywords", [])]
    by_keyword = not keyword or any(keyword in w or w in keyword for w in words if w)
    return by_keyword and (not region or region in (row.get("region") or ""))


def _start_date(text: str) -> date | None:
    """ "2026-11-09 ~ ..."·"2026-11-12 오후 2:00"의 앞 날짜."""
    try:
        return date.fromisoformat(text[:DATE_LENGTH])
    except ValueError:
        return None


def _in_range(text: str, start: date | None, end: date | None) -> bool:
    """요청한 기간 안에 시작하는지. 기간을 주지 않으면 거르지 않습니다."""
    if start is None and end is None:
        return True
    begins = _start_date(text)
    return begins is not None and (not start or start <= begins) and (not end or begins <= end)


def _page[T](rows: list[T], page: int) -> list[T]:
    return rows[(page - 1) * work24_api.PAGE_SIZE : page * work24_api.PAGE_SIZE]


def search_trainings(
    keyword: str | None,
    region: str | None,
    today: date,
    now: datetime,
    page: int = 1,
    date_from: date | None = None,
    date_to: date | None = None,
) -> TrainingList:
    """키워드로 훈련과정을 찾습니다. 추천(F-30)과 대화 도구도 이 함수를 씁니다.

    기간을 비우면 실시간 조회는 오늘부터 60일, 스냅샷은 기간으로
    거르지 않습니다(시연 날짜와 무관하게 보이도록).
    """
    start = date_from or today
    end = date_to or start + timedelta(days=work24_api.TRAINING_SEARCH_DAYS)
    # 지역은 고용24 지역 코드로 바꿔 검색 조건으로 넘깁니다(전체 건수·페이지가 그 지역 기준).
    area = work24_codes.region_code(region) if region else None
    live = work24_api.fetch_trainings(keyword, start, end, page, region=area)
    if live is not None:
        if region and area is None:
            # 코드로 정할 수 없는 지역("중구"처럼 여러 곳)은 받은 페이지에서 이름으로만 거릅니다.
            items = [t for t in live.items if region in (t.region or "")]
            return TrainingList(
                items=items, total=len(items), source=ExternalSource.LIVE, fetched_at=now
            )
        return TrainingList(
            items=live.items, total=live.total, source=ExternalSource.LIVE, fetched_at=now
        )
    snapshot = _snapshot("trainings")
    if snapshot is None:
        raise ExternalUnavailableError()
    rows = [
        r
        for r in snapshot["items"]
        if _matches(r, keyword, region) and _in_range(r["period"], date_from, date_to)
    ]
    items = [
        Training.model_validate({k: v for k, v in r.items() if k != "keywords"})
        for r in _page(rows, page)
    ]
    return TrainingList(
        items=items,
        total=len(rows),
        source=ExternalSource.SNAPSHOT,
        fetched_at=datetime.fromisoformat(snapshot["fetched_at"]),
    )


def search_programs(
    start: date | None, now: datetime, end: date | None = None, page: int = 1
) -> ProgramList:
    """start에 시작하는 프로그램. end가 있으면 그날까지 시작하는 것만 남깁니다."""
    live = work24_api.fetch_programs(start, page)
    if live is not None:
        items = [p for p in live.items if _in_range(p.schedule, None, end)]
        total = len(items) if end else live.total
        return ProgramList(items=items, total=total, source=ExternalSource.LIVE, fetched_at=now)
    snapshot = _snapshot("programs")
    if snapshot is None:
        raise ExternalUnavailableError()
    rows = [r for r in snapshot["items"] if _in_range(r["schedule"], start, end)]
    return ProgramList(
        items=[Program(**row) for row in _page(rows, page)],
        total=len(rows),
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
    date_from: date | None = None,
    date_to: date | None = None,
) -> TrainingList:
    keyword = occupation or desired_occupation(db, account.user_id)
    return search_trainings(keyword, region, now.date(), now, page, date_from, date_to)


def list_programs(
    start: date | None, now: datetime, end: date | None = None, page: int = 1
) -> ProgramList:
    return search_programs(start, now, end, page)
