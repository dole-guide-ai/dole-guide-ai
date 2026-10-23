"""회차 점검 · 활동 기록 · 활동 빼기 통합 테스트 (F-18·F-17·F-20).

이정호 seed: 오늘(2026-10-21) 기준 8일 전 고용24 OO물류와 기업 홈페이지 OO상사 지원.
"""

from collections.abc import Callable
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration

TODAY = date(2026, 10, 21)
CHECK = "/accounts/lee/rounds/current"
ACTIVITIES = "/accounts/lee/activities"
Headers = Callable[[str], dict[str, str]]


def _record(client: TestClient, headers: dict[str, str], **body):
    payload = {
        "activity_date": TODAY.isoformat(),
        "kind": "job_application",
        "route": "work24",
        "org_name": "OO물산",
        **body,
    }
    return client.post(ACTIVITIES, headers=headers, json=payload)


def _by_org(check: dict) -> dict[str, str]:
    return {a["org_name"]: a["status"] for a in check["activities"]}


def _round_check(res) -> dict:
    return next(u["value"] for u in res.json()["updates"] if u["path"] == "/round_check")


def test_lee_needs_one_more_and_same_day_is_excluded(client: TestClient, entered_headers: Headers):
    """F-18 완료 기준: 인정 1건 · 1건 더, OO상사는 같은 날 · 계산 제외와 W1."""
    check = client.get(CHECK, headers=entered_headers("lee")).json()

    assert (check["required"], check["required_job_search"]) == (2, 1)
    assert (check["counted"], check["remaining"]) == (1, 1)
    assert check["check_status"] == "short"
    assert _by_org(check) == {"OO물류": "counted", "OO상사": "same_day"}
    assert {w["id"] for w in check["warnings"]} >= {"W1", "W5"}
    assert check["rule_review"] == "not_verified"
    assert "ACT-055" in check["rule_refs"]


def test_recording_today_makes_round_satisfied(client: TestClient, entered_headers: Headers):
    """F-17 완료 기준: 오늘 고용24 지원을 기록하면 충족. 같은 활동은 다시 넣지 않음."""
    headers = entered_headers("lee")

    res = _record(client, headers)

    assert res.status_code == 201
    added = res.json()["updates"][0]["value"]
    assert (added["category"], added["source"], added["planned"]) == ("job_search", "direct", False)
    assert _round_check(res)["check_status"] == "satisfied"
    again = _record(client, headers, org_name="OO 물산")
    assert again.status_code == 409
    assert again.json()["code"] == "DUPLICATE_ACTIVITY"


def test_future_date_is_planned(client: TestClient, entered_headers: Headers):
    res = _record(client, entered_headers("lee"), activity_date=str(TODAY + timedelta(days=2)))

    assert res.json()["updates"][0]["value"]["planned"] is True
    assert _round_check(res)["counted"] == 1


def test_unknown_kind_needs_category(client: TestClient, entered_headers: Headers):
    headers = entered_headers("lee")

    missing = _record(client, headers, kind="job_request_upgrade", route=None)
    given = _record(
        client, headers, kind="job_request_upgrade", route=None, category="non_job_search"
    )

    assert missing.status_code == 422
    assert given.status_code == 201
    assert _by_org(_round_check(given))["OO물산"] == "needs_check"


def test_past_round_date_is_closed(client: TestClient, entered_headers: Headers):
    headers = entered_headers("lee")
    period_start = date.fromisoformat(client.get(CHECK, headers=headers).json()["period_start"])

    res = _record(client, headers, activity_date=str(period_start - timedelta(days=1)))

    assert res.status_code == 409
    assert res.json()["code"] == "ROUND_CLOSED"


def test_deleting_representative_counts_the_other(client: TestClient, entered_headers: Headers):
    """F-20 완료 기준: 12.08 OO물류를 빼면 OO상사가 인정 계산으로 바뀝니다."""
    headers = entered_headers("lee")
    activities = client.get(ACTIVITIES, headers=headers).json()["items"]
    logistics = next(a for a in activities if a["org_name"] == "OO물류")

    res = client.delete(f"{ACTIVITIES}/{logistics['activity_id']}", headers=headers)

    assert res.status_code == 200
    removed = res.json()["updates"][0]
    assert (removed["path"], removed["op"]) == (f"/activities/{logistics['activity_id']}", "remove")
    assert _by_org(_round_check(res)) == {"OO상사": "counted"}
    assert (
        client.delete(f"{ACTIVITIES}/{logistics['activity_id']}", headers=headers).status_code
        == 404
    )


def test_activity_list_has_round_and_status(client: TestClient, entered_headers: Headers):
    headers = entered_headers("lee")
    check = client.get(CHECK, headers=headers).json()

    items = client.get(ACTIVITIES, headers=headers, params={"round": check["round"]}).json()[
        "items"
    ]

    assert {a["org_name"]: (a["round"], a["status"]) for a in items} == {
        "OO물류": (check["round"], "counted"),
        "OO상사": (check["round"], "same_day"),
    }


def test_other_visitor_cannot_delete(client: TestClient, entered_headers: Headers):
    headers = entered_headers("lee")
    activity_id = client.get(ACTIVITIES, headers=headers).json()["items"][0]["activity_id"]

    res = client.delete(f"{ACTIVITIES}/{activity_id}", headers=entered_headers("lee"))

    assert res.status_code == 404
    assert res.json()["code"] == "NOT_FOUND"


def test_account_without_round_has_no_current_check(client: TestClient, entered_headers: Headers):
    res = client.get("/accounts/park/rounds/current", headers=entered_headers("park"))

    assert res.status_code == 404
    assert res.json()["code"] == "NO_ACTIVE_ROUND"
