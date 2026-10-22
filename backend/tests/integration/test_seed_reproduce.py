"""N-04: 다른 날 처음부터 다시 해도 같은 분기·패널·회차가 나오는지 확인합니다.

seed 날짜는 입장일 기준 상대값입니다. 입장일을 요일·공휴일·월말·윤년이 다른 날로 바꿔 계정을 만들고,
응답의 날짜를 입장일과의 차이(일)로 바꿔 비교합니다.

같아야 하는 것: 진입 분기·화면 설정·절차 단계, 지난 회차와 이번 회차(날짜·출석·신청 상태).
달라도 되는 것: 앞으로 올 회차의 날짜와 수급기간 끝날. 실제 달력(주말·공휴일 미루기, 윤년)으로
계산하므로 입장일에 따라 하루~며칠 밀립니다. 안내 문구 속 실제 날짜(예: 10.27)도 다릅니다.
"""

import re
from datetime import date, datetime, time
from typing import Any

import pytest
from sqlalchemy.orm import Session

from app.core.clock import KST
from app.services import accounts as account_service
from app.services.seed import load_personas, read_seed_file
from app.services.visitors import authenticate, create_visitor
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration

ANCHORS = [
    date(2026, 10, 24),  # 토요일
    date(2026, 12, 31),  # 연말 (다음 날 신정)
    date(2027, 2, 6),  # 설 연휴 직전
    date(2028, 2, 29),  # 윤일
    date(2026, 9, 24),  # 추석 연휴 직전
]
PERSONAS = [p["persona_id"] for p in read_seed_file()]
# 실제 달력으로 계산해 입장일마다 달라도 되는 값
CALENDAR_FIELDS = {"period_end_date", "expected_end_date"}
_DATE_IN_TEXT = re.compile(r"\d{2}\.\d{2}")


def _relative(value: Any, anchor: date) -> Any:
    """응답 안의 날짜를 입장일과의 차이(일)로 바꿉니다. 나머지 값은 그대로 둡니다."""
    if isinstance(value, datetime):
        return ("dt", (value.astimezone(KST).date() - anchor).days, value.astimezone(KST).time())
    if isinstance(value, date):
        return ("d", (value - anchor).days)
    if isinstance(value, str):
        return _DATE_IN_TEXT.sub("MM.DD", value)
    if isinstance(value, dict):
        return {k: _relative(v, anchor) for k, v in value.items() if k not in CALENDAR_FIELDS}
    if isinstance(value, list):
        return [_relative(v, anchor) for v in value]
    return value


def _snapshot(db: Session, persona_id: str, anchor: date) -> dict[str, Any]:
    now = datetime.combine(anchor, time(9), KST)
    visitor = create_visitor(db, now)
    ctx = authenticate(db, visitor.visitor_token, now)
    account, _ = account_service.enter(db, ctx.visitor_id, persona_id, anchor)
    found = account_service.find_account(db, ctx.visitor_id, persona_id)
    rounds = account_service.read_rounds(db, found.user_id, anchor)
    return _relative(
        {
            "account": account.model_dump(),
            # 앞으로 올 회차는 개수·상태만 비교합니다(날짜는 달력에 따라 밀림).
            "rounds": [
                r.model_dump() if r.status != "upcoming" else {"round": r.round, "status": r.status}
                for r in rounds
            ],
        },
        anchor,
    )


@pytest.mark.parametrize("persona_id", PERSONAS)
@pytest.mark.parametrize("anchor", ANCHORS, ids=str)
def test_same_situation_on_any_entry_day(db_session: Session, persona_id: str, anchor: date):
    load_personas(db_session)

    expected = _snapshot(db_session, persona_id, TEST_TODAY)
    actual = _snapshot(db_session, persona_id, anchor)

    assert actual == expected
