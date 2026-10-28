from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

from app.rules.resume import REQUIRED_SECTIONS

pytestmark = pytest.mark.integration

# 박진수(합성) 이력서의 꼭 묻는 5개를 채우는 직접 고치기
FILL = {
    "/resume_title": "제조 생산직 22년 경력 이력서",
    "/education/e1/education_level": "고등학교",
    "/education/e1/graduation_status": "졸업",
    "/education/e1/school_name": "OO고등학교",
    "/education/e1/start_date": "1981-03",
    "/education/e1/end_date": "1984-02",
    "/job_preferences/desired_occupations/o1/occupation": {
        "code": None,
        "name": "프레스 반장",
        "status": "name_only",
    },
    "/job_preferences/desired_occupations/o1/experience_type": "경력",
    "/job_preferences/desired_regions": [
        {"code": "41550", "name": "경기 안성시", "status": "confirmed", "said": "안성"}
    ],
    "/job_preferences/desired_salary": {"amount": 2800000, "unit": "monthly"},
    "/job_preferences/employment_contract_type": "기간의 정함이 없는 근로계약",
    "/job_preferences/military_alternative": "해당 없음",
    "/careers/c1/company_name": "OO산업",
    "/careers/c1/start_date": "2004-03",
    "/careers/c1/end_date": "2026-09",
    "/careers/c1/position": "반장",
    "/careers/c1/main_duties": "프레스 라인 운영",
    "/certifications/l1/certificate_name": "지게차운전기능사",
}


def _patch(client: TestClient, headers: dict, ops: list[dict], if_match: str | None = None):
    """If-Match를 주지 않으면 지금 ETag를 받아 보냅니다(REST는 If-Match 필수, 설계 3.11)."""
    if if_match is None:
        if_match = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    return client.patch("/accounts/park/resume", json=ops, headers=headers | {"If-Match": if_match})


def test_empty_resume_then_fill_and_save(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    res = client.get("/accounts/park/resume", headers=headers)
    assert res.status_code == 200 and res.headers["ETag"] == '"0"'
    body = res.json()
    assert body["completeness"]["filled"] == 0 and not body["can_save"]
    # 항목별 완료 여부도 서버가 판정해 내려 줍니다(화면은 그대로 씀).
    assert body["completeness"]["sections"] == dict.fromkeys(REQUIRED_SECTIONS, False)
    assert body["next_question"] == "resume.career_new"

    not_ready = _patch(client, headers, [{"op": "replace", "path": "/status", "value": "saved"}])
    assert not_ready.status_code == 409 and not_ready.json()["code"] == "RESUME_NOT_READY"

    ops = [{"op": "replace", "path": p, "value": v} for p, v in FILL.items()]
    filled = _patch(client, headers, ops, if_match='"0"')
    assert filled.status_code == 200, filled.text
    read = client.get("/accounts/park/resume", headers=headers).json()
    assert read["completeness"]["filled"] == 5 and read["can_save"], read["next_question"]
    assert read["data"]["careers"][0]["company_name"]["source"] == "direct"

    saved = _patch(client, headers, [{"op": "replace", "path": "/status", "value": "saved"}])
    assert saved.status_code == 200, saved.text
    entry = saved.json()["entry"]
    assert (entry["branch_id"], entry["panel"], entry["progress"]["done"]) == ("E6", "E", [1])
    ids = [m["template_id"] for m in entry["messages"]]
    assert ids[:2] == ["T-SAVE-E7a", "T-WORK24-HINT"]
    hint = entry["messages"][1]["text"]
    assert "월급 단위" in hint and "프레스 반장" in hint and "학점" not in hint
    assert client.get("/accounts/park/resume", headers=headers).json()["status"] == "saved"

    # 저장한 뒤 칸을 고치면 다시 초안
    _patch(client, headers, [{"op": "remove", "path": "/resume_title"}])
    again = client.get("/accounts/park/resume", headers=headers).json()
    assert again["status"] == "draft" and not again["can_save"]


def test_version_conflict_and_status_with_fields(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    one = [{"op": "replace", "path": "/resume_title", "value": "제목"}]
    assert _patch(client, headers, one, if_match='"5"').json()["code"] == "VERSION_CONFLICT"
    mixed = one + [{"op": "replace", "path": "/status", "value": "saved"}]
    res = _patch(client, headers, mixed)
    assert res.status_code == 422 and res.json()["code"] == "STATUS_WITH_FIELDS"


def test_patch_without_if_match_is_conflict(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """REST 서류 PATCH는 If-Match가 필수입니다 (설계 3.11). 없으면 409."""
    res = client.patch(
        "/accounts/park/resume",
        headers=entered_headers("park"),
        json=[{"op": "replace", "path": "/status", "value": "saved"}],
    )

    assert res.status_code == 409
    assert res.json()["code"] == "VERSION_CONFLICT"


def test_direct_pick_of_occupations_and_regions_is_checked_by_server(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    """패널 드롭다운에서 고른 코드: 서버가 코드표로 이름·상태를 정하고, 뺀 직종은 지웁니다."""
    headers = entered_headers("park")
    occupations = "/job_preferences/desired_occupations"
    ops = [
        {"op": "replace", "path": occupations, "value": [{"code": "834001"}, {"name": "경비"}]},
        {"op": "replace", "path": "/job_preferences/desired_regions", "value": [{"code": "11350"}]},
    ]
    assert _patch(client, headers, ops).status_code == 200
    prefs = client.get("/accounts/park/resume", headers=headers).json()["data"]["job_preferences"]
    assert [d["occupation"]["value"]["status"] for d in prefs["desired_occupations"]] == [
        "confirmed",
        "name_only",
    ]
    assert prefs["desired_regions"]["value"][0]["name"] == "서울 노원구"

    keep = [{"op": "replace", "path": occupations, "value": [{"code": "834001"}]}]
    res = _patch(client, headers, keep)
    assert res.status_code == 200
    # 목록에서 뺀 직종의 칸은 remove 갱신으로 알립니다.
    assert any(u["op"] == "remove" for u in res.json()["updates"])
    prefs = client.get("/accounts/park/resume", headers=headers).json()["data"]["job_preferences"]
    assert [d["occupation"]["value"]["name"] for d in prefs["desired_occupations"]] == [
        "아파트 전기관리원"
    ]

    bad = [{"op": "replace", "path": occupations, "value": [{"code": "999999"}]}]
    res = _patch(client, headers, bad)
    assert res.status_code == 422
    assert res.json()["details"] == [{"field": "patch[0]", "type": "code"}]


def test_direct_gpa_over_the_scale_is_422(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    base = "/education/e1"
    level = [{"op": "replace", "path": f"{base}/education_level", "value": "대학교(4년제)"}]
    assert _patch(client, headers, level).status_code == 200

    over = [
        {"op": "replace", "path": f"{base}/gpa_scale", "value": "4.5점"},
        {"op": "replace", "path": f"{base}/gpa", "value": "4.7"},
    ]
    res = _patch(client, headers, over)
    assert res.status_code == 422
    assert res.json()["message"] == "학점은 0~4.5점 사이로 적어 주세요."
    assert res.json()["details"] == [{"field": "patch[1]", "type": "number"}]

    ok = [over[0], {"op": "replace", "path": f"{base}/gpa", "value": "3.8"}]
    assert _patch(client, headers, ok).status_code == 200
    bad_scale = [{"op": "replace", "path": f"{base}/gpa_scale", "value": "4.8"}]
    res = _patch(client, headers, bad_scale)
    assert res.status_code == 422 and res.json()["message"].startswith("학점 만점은 4.0·4.3")
    # 학점 3.8은 두고 만점만 4.0으로 낮추면 되지만, 학점이 새 만점을 넘으면 막습니다.
    assert _patch(client, headers, [{**over[0], "value": "4.0"}]).status_code == 200
    high = [over[0], {"op": "replace", "path": f"{base}/gpa", "value": "4.3"}]
    assert _patch(client, headers, high).status_code == 200
    # 같은 PATCH에서 만점을 다시 낮추면 마지막 값(4.0)으로 학점 4.3을 봅니다.
    repeated = [*high, {"op": "replace", "path": f"{base}/gpa_scale", "value": "4.0"}]
    res = _patch(client, headers, repeated)
    assert res.status_code == 422 and res.json()["details"] == [
        {"field": "patch[2]", "type": "number"}
    ]
    lower = [{"op": "replace", "path": f"{base}/gpa_scale", "value": "4.0"}]
    res = _patch(client, headers, lower)
    assert res.status_code == 422 and res.json()["message"] == "학점은 0~4.0점 사이로 적어 주세요."
