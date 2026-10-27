"""회차 신청서 조회 통합 테스트 (F-23)."""

from collections.abc import Callable, Iterator
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.clock import KST, get_now
from app.main import app

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def fixed_now(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """제출 방식은 지금 시각으로 정하므로 오늘(2026-10-21) 오전 10시로 고정합니다."""
    monkeypatch.setitem(
        app.dependency_overrides, get_now, lambda: datetime(2026, 10, 21, 10, tzinfo=KST)
    )
    yield


def test_lee_current_application_uses_recorded_activities(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")

    res = client.get("/accounts/lee/rounds/current/application", headers=headers)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["round"] == 4
    assert body["status"] == "draft"
    assert body["attendance_required"] is True
    assert (body["required_activities"], body["required_job_search"]) == (2, 1)
    # 인정·부족 건수도 회차 점검과 같은 계산으로 내려 줍니다(화면이 행 개수로 세지 않게).
    check = client.get("/accounts/lee/rounds/current", headers=headers).json()
    assert (body["counted_activities"], body["remaining_activities"]) == (
        check["counted"],
        check["remaining"],
    )
    assert body["remaining_job_search"] == check["remaining_job_search"]
    # seed: 같은 날 OO물류(고용24 불러오기)·OO상사 → OO물류만 신청서, OO상사는 참고
    assert [r["company_name"] for r in body["job_search_rows"]] == ["OO물류"]
    assert body["job_search_rows"][0]["application_method"] == "고용24(워크넷)"
    assert [r["company_name"] for r in body["excluded_rows"]] == ["OO상사"]
    # 3차에 답한 통지 방법·실업크레딧을 불러옵니다
    assert body["data"]["notification_method"]["value"] == "sms"
    assert body["data"]["notification_method"]["source"] == "user_answer"
    assert body["data"]["credit"]["application"]["value"] == "wish"
    assert body["profile_display"]["account_last4"]
    assert body["locked_reason"] is None
    # 4차는 출석 회차라 출석 준비 확인. 본인 답변이 비어 있어 아직 막힘 (F-26)
    assert body["submit_mode"] == "attend"
    assert body["can_submit"] is False
    blocking = [item["key"] for item in body["checklist"]["blocking"]]
    assert blocking == ["self_answers", "job_search_fields", "next_activity"]
    # OO물류 1건만 인정 → 4차 필요 2건에 1건 부족은 경고
    assert [item["key"] for item in body["checklist"]["warnings"]] == ["requirement_met"]


def test_round_number_and_missing_round(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")

    third = client.get("/accounts/lee/rounds/3/application", headers=headers).json()
    assert third["round"] == 3
    assert third["status"] == "submitted"

    res = client.get("/accounts/lee/rounds/40/application", headers=headers)
    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_account_without_rounds_has_no_current_application(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")

    res = client.get("/accounts/park/rounds/current/application", headers=headers)

    assert res.status_code == 404
    assert res.json()["code"] == "NO_ACTIVE_ROUND"
