"""이력서 대화를 코드가 이끄는지: 다음 질문은 턴 끝에 코드가 내고, 정해진 선택지 답은 모델 없이."""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

pytestmark = pytest.mark.integration

# 경력·학력·희망 조건을 채운 이력서(자격·그 밖의 역량은 비움). 합성 값만 씁니다.
FILLED = {
    "/resume_title": "물류 경력 이력서",
    "/education/e1/education_level": "고등학교",
    "/education/e1/graduation_status": "졸업",
    "/education/e1/school_name": "OO고등학교",
    "/education/e1/start_date": "1981-03",
    "/education/e1/end_date": "1984-02",
    "/job_preferences/desired_occupations/o1/occupation": {
        "code": None,
        "name": "물류",
        "status": "name_only",
    },
    "/job_preferences/desired_occupations/o1/experience_type": "경력",
    "/job_preferences/desired_regions": [{"code": None, "name": "인천"}],
    "/job_preferences/desired_salary": {"amount": 2800000, "unit": "monthly"},
    "/job_preferences/employment_contract_type": "기간의 정함이 없는 근로계약",
    "/job_preferences/military_alternative": "해당 없음",
    "/careers/c1/company_name": "OO물류",
    "/careers/c1/start_date": "2012-03",
    "/careers/c1/end_date": "2026-09",
    "/careers/c1/position": "반장",
    "/careers/c1/main_duties": "창고 입출고 관리",
}


def sse_events(res) -> list[tuple[str, dict]]:
    out, name = [], None
    for line in res.text.splitlines():
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            out.append((name, json.loads(line.split(":", 1)[1].strip())))
    return out


def send(client: TestClient, headers: dict, text: str) -> list[tuple[str, dict]]:
    return sse_events(client.post("/accounts/park/messages", headers=headers, json={"text": text}))


def asked(events: list[tuple[str, dict]]) -> dict:
    return next(data for name, data in events if name == "ask_user")


def test_code_asks_next_resume_question_after_answer(client, entered_headers, fake_agent_llm):
    model = fake_agent_llm([AIMessage("이력서를 같이 써 볼게요.")], route="resume")
    headers = entered_headers("park")

    events = send(client, headers, "이력서 쓸게요")

    names = [name for name, _ in events]
    assert names[-1] == "done" and "ask_user" in names
    question = asked(events)
    assert question["question_id"] == "resume.career_new"
    assert question["text"].startswith("가장 최근에 일하신 곳은 어디예요?")
    assert question["import_kind"] == "career_certificate" and question["accepts_file"]
    assert model.calls == 1
    # 새로고침하면 마지막 말풍선이 질문이라 질문 카드가 다시 뜹니다.
    pending = client.get("/accounts/park", headers=headers).json()["pending_ask"]
    assert pending["question_id"] == "resume.career_new"


def test_fixed_choice_answers_skip_the_model(client, entered_headers, fake_agent_llm):
    model = fake_agent_llm([AIMessage("경력을 확인했어요.")], route="resume")
    headers = entered_headers("park")
    etag = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    ops = [{"op": "replace", "path": p, "value": v} for p, v in FILLED.items()]
    res = client.patch("/accounts/park/resume", json=ops, headers=headers | {"If-Match": etag})
    assert res.status_code == 200, res.text

    # 경력을 채운 뒤에는 그 전 경력을 한 번 묻습니다.
    first = asked(send(client, headers, "경력은 다 말씀드렸어요"))
    assert first["question_id"] == "resume.career_more"
    assert first["choices"] == ["네, 있어요", "없어요"]

    # "없어요"는 모델 없이 확인하고 다음 칸(자격증)으로 갑니다.
    events = send(client, headers, "없어요")
    tokens = "".join(data["text"] for name, data in events if name == "token")
    assert tokens == "경력은 지금 적은 회사까지로 둘게요."
    assert asked(events)["question_id"] == "resume.license"

    # 자격증 "없어요"는 코드가 해당 없음으로 저장합니다.
    events = send(client, headers, "없어요")
    updates = [data for name, data in events if name == "form_update"]
    assert any(u["path"].startswith("/certifications_status") for u in updates)
    assert asked(events)["question_id"] != "resume.license"
    assert model.calls == 1
    resume = client.get("/accounts/park/resume", headers=headers).json()
    assert resume["data"]["certifications_status"]["status"] == "not_applicable"


def test_none_answer_with_punctuation_is_saved_and_moves_on(
    client, entered_headers, fake_agent_llm
):
    model = fake_agent_llm([AIMessage("확인했어요.")], route="resume")
    headers = entered_headers("park")
    etag = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    ops = [
        {"op": "replace", "path": p, "value": v}
        for p, v in FILLED.items()
        if p != "/careers/c1/position"
    ]
    res = client.patch("/accounts/park/resume", json=ops, headers=headers | {"If-Match": etag})
    assert res.status_code == 200, res.text

    assert asked(send(client, headers, "다 말했어요"))["question_id"] == "resume.career_position"
    # 마침표가 붙어도 선택지 답으로 보고, 직급을 "없음"으로 저장한 뒤 다음 질문으로 갑니다.
    events = send(client, headers, "없었어요.")
    assert asked(events)["question_id"] != "resume.career_position"
    assert model.calls == 1
    careers = client.get("/accounts/park/resume", headers=headers).json()["data"]["careers"]
    assert careers[0]["position"]["value"] == "없음"


def test_no_career_since_old_resume_moves_on(client, entered_headers, fake_agent_llm):
    """최(예전 이력서 최신화): "그 뒤 경력 없어요"를 저장해 같은 질문이 되풀이되지 않습니다."""
    model = fake_agent_llm([AIMessage("이력서를 최신으로 고쳐 볼게요.")], route="resume")
    headers = entered_headers("choi")

    def send_choi(text: str) -> list[tuple[str, dict]]:
        res = client.post("/accounts/choi/messages", headers=headers, json={"text": text})
        return sse_events(res)

    assert asked(send_choi("이력서 고칠게요"))["question_id"] == "resume.career_since_old"
    events = send_choi("없어요")
    assert asked(events)["question_id"] != "resume.career_since_old"
    assert model.calls == 1
