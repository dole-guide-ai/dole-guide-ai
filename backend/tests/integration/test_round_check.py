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


def test_patching_activity_recounts_and_rederives_category(
    client: TestClient, entered_headers: Headers
):
    """F-12: 고치면 회차 점검을 다시 계산하고, kind를 바꾸면 구분도 다시 정합니다."""
    headers = entered_headers("lee")
    activities = client.get(ACTIVITIES, headers=headers).json()["items"]
    trading = next(a for a in activities if a["org_name"] == "OO상사")

    # 같은 날이라 빠졌던 OO상사를 다른 날로 옮기면 인정 계산이 됩니다.
    moved = client.patch(
        f"{ACTIVITIES}/{trading['activity_id']}",
        headers=headers,
        json=[{"op": "replace", "path": "/activity_date", "value": TODAY.isoformat()}],
    )
    assert moved.status_code == 200
    assert _by_org(_round_check(moved))["OO상사"] == "counted"
    assert _round_check(moved)["check_status"] == "satisfied"

    # 종류를 특강으로 바꾸면 구분이 구직 외 활동이 되고, 구직활동은 1건으로 줄어듭니다.
    lecture = client.patch(
        f"{ACTIVITIES}/{trading['activity_id']}",
        headers=headers,
        json=[{"op": "replace", "path": "/kind", "value": "lecture"}],
    )
    assert lecture.json()["updates"][0]["value"]["category"] == "non_job_search"
    assert _round_check(lecture)["counted_job_search"] == 1


def test_choice_fields_accept_only_work24_options(client: TestClient, entered_headers: Headers):
    """경로·구직 방법·응모 방식·활동 결과는 정해진 선택지만 받습니다 (데이터 설계 7.1)."""
    headers = entered_headers("lee")
    activity_id = client.get(ACTIVITIES, headers=headers).json()["items"][0]["activity_id"]
    url = f"{ACTIVITIES}/{activity_id}"

    bad = client.patch(
        url, headers=headers, json=[{"op": "replace", "path": "/result", "value": "합격"}]
    )
    ok = client.patch(
        url, headers=headers, json=[{"op": "replace", "path": "/result", "value": "최종 불합격"}]
    )

    assert bad.status_code == 422
    assert bad.json()["details"] == [{"field": "patch[0]", "type": "choice"}]
    assert ok.status_code == 200
    assert _record(client, headers, route="job_site").status_code == 422


def test_contact_saves_department_not_name(client: TestClient, entered_headers: Headers):
    """F-25: '김OO 과장님'이라고 해도 이름은 저장되지 않고 부서명만 남습니다."""
    headers = entered_headers("lee")
    activity_id = client.get(ACTIVITIES, headers=headers).json()["items"][0]["activity_id"]
    url = f"{ACTIVITIES}/{activity_id}"

    def contact(value: str):
        return client.patch(
            url, headers=headers, json=[{"op": "replace", "path": "/contact_dept", "value": value}]
        )

    assert contact("김OO 과장님").status_code == 422
    saved = contact("인사팀 김OO 과장님")
    assert saved.json()["updates"][0]["value"]["contact_dept"] == "인사팀"
