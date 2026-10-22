"""절차 상태 조회와 수급 종료 진단 통합 테스트 (F-33)."""

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.clock import get_today
from app.main import app

pytestmark = pytest.mark.integration


def test_procedure_shows_end_date_and_remaining_rounds(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    body = client.get("/accounts/lee/procedure", headers=headers).json()

    applied = date.fromisoformat(body["eligibility_applied_on"])
    # 이정호(270일): 대기기간이 끝난 다음 날 + 269일 (완료 기준)
    assert body["benefit_days"] == 270
    assert body["benefit_end_date"] == (applied + timedelta(days=7 + 269)).isoformat()
    assert body["expected_end_date"] == min(body["benefit_end_date"], body["period_end_date"])
    rounds = client.get("/accounts/lee/rounds", headers=headers).json()["items"]
    assert body["last_round"] == len(rounds)
    assert body["remaining_rounds"] == sum(1 for r in rounds if r["status"] != "closed")


def test_account_ends_after_expected_end_date(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("lee")
    end = date.fromisoformat(
        client.get("/accounts/lee/procedure", headers=headers).json()["expected_end_date"]
    )
    rounds = client.get("/accounts/lee/rounds", headers=headers).json()["items"]
    last_recognition = date.fromisoformat(rounds[-1]["recognition_date"])

    # 종료 예정일이 지나도 마지막 회차 인정일 전이면 아직 실업인정 중입니다.
    app.dependency_overrides[get_today] = lambda: end + timedelta(days=1)
    if last_recognition > end:
        assert client.get("/accounts/lee", headers=headers).json()["procedure"]["stage"] == (
            "recognition"
        )

    app.dependency_overrides[get_today] = lambda: max(end, last_recognition) + timedelta(days=1)
    body = client.get("/accounts/lee", headers=headers).json()

    assert body["procedure"]["stage"] == "ended"
    assert body["procedure"]["end_reason"] in ("exhausted", "period_expired")
    assert body["procedure"]["remaining_rounds"] == 0
    assert body["entry"]["branch_id"] == "END"
    assert body["entry"]["messages"][0]["template_id"] == "T-END"
