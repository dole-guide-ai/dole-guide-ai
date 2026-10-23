from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

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
    "/job_preferences/desired_regions": [{"code": None, "name": "경기 안성시"}],
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
    extra = {"If-Match": if_match} if if_match else {}
    return client.patch("/accounts/park/resume", json=ops, headers=headers | extra)


def test_empty_resume_then_fill_and_save(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    res = client.get("/accounts/park/resume", headers=headers)
    assert res.status_code == 200 and res.headers["ETag"] == '"0"'
    body = res.json()
    assert body["completeness"] == {"filled": 0, "total": 5} and not body["can_save"]
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


def test_version_conflict_and_status_with_fields(
    client: TestClient, entered_headers: Callable[[str], dict[str, str]]
) -> None:
    headers = entered_headers("park")
    one = [{"op": "replace", "path": "/resume_title", "value": "제목"}]
    assert _patch(client, headers, one, if_match='"5"').json()["code"] == "VERSION_CONFLICT"
    mixed = one + [{"op": "replace", "path": "/status", "value": "saved"}]
    res = _patch(client, headers, mixed)
    assert res.status_code == 422 and res.json()["code"] == "STATUS_WITH_FIELDS"
