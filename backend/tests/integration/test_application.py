"""회차 신청서 조회 통합 테스트 (F-23)."""

from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration


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
