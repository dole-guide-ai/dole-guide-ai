"""이력서 대화: 버튼 답·제안은 코드가 저장하고, 모델이 묻지 않으면 코드가 다음 칸을 묻습니다."""

import json

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from app.agent.checkpointer import get_checkpointer

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


def fill(client: TestClient, headers: dict, skip: tuple[str, ...] = ()) -> None:
    etag = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    ops = [{"op": "replace", "path": p, "value": v} for p, v in FILLED.items() if p not in skip]
    res = client.patch("/accounts/park/resume", json=ops, headers=headers | {"If-Match": etag})
    assert res.status_code == 200, res.text


def resume_data(client: TestClient, headers: dict) -> dict:
    return client.get("/accounts/park/resume", headers=headers).json()["data"]


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


def test_button_answers_are_saved_by_code(client, entered_headers, fake_agent_llm):
    """버튼 답은 코드가 저장하고(모델이 해석하지 않음), 모델은 확인하고 다음으로 넘깁니다."""
    model = fake_agent_llm([AIMessage("확인했어요.")], route="resume")
    headers = entered_headers("park")
    fill(client, headers)

    # 경력을 채운 뒤에는 그 전 경력을 한 번 묻습니다.
    first = asked(send(client, headers, "경력은 다 말씀드렸어요"))
    assert first["question_id"] == "resume.career_more"
    assert first["choices"] == ["네, 있어요", "없어요"]
    assert asked(send(client, headers, "없어요"))["question_id"] == "resume.license"

    # 자격증 "없어요"는 코드가 해당 없음으로 저장합니다.
    events = send(client, headers, "없어요")
    updates = [data for name, data in events if name == "form_update"]
    assert any(u["path"].startswith("/certifications_status") for u in updates)
    assert asked(events)["question_id"] != "resume.license"
    assert model.calls == 3  # 턴마다 한 번(확인·다음 칸 제안), 분류는 부르지 않음
    assert resume_data(client, headers)["certifications_status"]["status"] == "not_applicable"


def test_none_answer_with_punctuation_is_saved_and_moves_on(
    client, entered_headers, fake_agent_llm
):
    fake_agent_llm([AIMessage("확인했어요.")], route="resume")
    headers = entered_headers("park")
    fill(client, headers, skip=("/careers/c1/position",))

    assert asked(send(client, headers, "다 말했어요"))["question_id"] == "resume.career_position:c1"
    # 마침표가 붙어도 버튼 답으로 보고, 직급을 "없음"으로 저장한 뒤 다음 질문으로 갑니다.
    events = send(client, headers, "없었어요.")
    assert asked(events)["question_id"] != "resume.career_position:c1"
    assert resume_data(client, headers)["careers"][0]["position"]["value"] == "없음"


def test_unknown_answer_defers_and_moves_to_the_next_field(client, entered_headers, fake_agent_llm):
    """모르는 칸에서 멈추지 않습니다(인터뷰 I-01: 입학 연도를 몰라 같은 질문을 되풀이)."""
    fake_agent_llm([AIMessage("괜찮아요.")], route="resume")
    headers = entered_headers("park")
    fill(client, headers, skip=("/education/e1/start_date", "/education/e1/end_date"))
    send(client, headers, "다 말했어요")  # 그 전 경력
    assert asked(send(client, headers, "없어요"))["question_id"] == "resume.license"
    detail = asked(send(client, headers, "없어요"))
    assert detail["question_id"] == "resume.education_period:e1"
    assert detail["choices"] == ["기억이 안 나요"]

    events = send(client, headers, "기억이 안 나요")

    assert asked(events)["question_id"] != "resume.education_period:e1"


def test_proposal_from_career_is_saved_when_accepted(client, entered_headers, fake_agent_llm):
    fake_agent_llm([AIMessage("좋아요.")], route="resume")
    headers = entered_headers("park")
    occupation = "/careers/c1/occupation"
    skip = tuple(p for p in FILLED if p.startswith("/job_preferences"))
    fill(client, headers, skip=skip)
    etag = client.get("/accounts/park/resume", headers=headers).headers["ETag"]
    op = [{"op": "replace", "path": occupation, "value": {"code": None, "name": "물류"}}]
    client.patch("/accounts/park/resume", json=op, headers=headers | {"If-Match": etag})
    send(client, headers, "다 말했어요")  # 그 전 경력
    send(client, headers, "없어요")  # 자격증
    question = asked(send(client, headers, "없어요"))
    assert question["question_id"] == "resume.wish_job"
    assert question["choices"][0] == "네, 좋아요"

    send(client, headers, "네, 좋아요")

    occupations = resume_data(client, headers)["job_preferences"]["desired_occupations"]
    assert occupations[0]["occupation"]["value"]["name"] == "물류"


def test_no_career_since_old_resume_moves_on(client, entered_headers, fake_agent_llm):
    """최(예전 이력서 최신화): "그 뒤 경력 없어요"를 저장해 같은 질문이 되풀이되지 않습니다."""
    fake_agent_llm([AIMessage("이력서를 최신으로 고쳐 볼게요.")], route="resume")
    headers = entered_headers("choi")

    def send_choi(text: str) -> list[tuple[str, dict]]:
        res = client.post("/accounts/choi/messages", headers=headers, json={"text": text})
        return sse_events(res)

    assert asked(send_choi("이력서 고칠게요"))["question_id"] == "resume.career_since_old"
    events = send_choi("없어요")
    assert asked(events)["question_id"] != "resume.career_since_old"


def test_reset_clears_conversation_state(client, entered_headers, fake_agent_llm, monkeypatch):
    """개발용 처음부터 다시(DELETE → PUT): 대화 그래프 상태도 지워 지난 질문을 잇지 않습니다."""
    saver = get_checkpointer()
    deleted: list[str] = []
    delete_thread = saver.delete_thread
    monkeypatch.setattr(
        saver, "delete_thread", lambda tid: (deleted.append(tid), delete_thread(tid))
    )
    fake_agent_llm([AIMessage("이력서를 같이 써 볼게요.")], route="resume")
    headers = entered_headers("park")
    send(client, headers, "이력서 쓸게요")
    assert client.get("/accounts/park", headers=headers).json()["pending_ask"]

    assert client.delete("/accounts/park", headers=headers).status_code == 204
    again = client.put("/accounts/park", headers=headers).json()

    assert saver.get_tuple({"configurable": {"thread_id": deleted[0]}}) is None
    assert again["pending_ask"] is None
    assert again["entry"]["messages"][0]["template_id"] == "T-INTRO"


def test_free_text_answer_is_read_then_saved_by_code(client, entered_headers, fake_agent_llm):
    """자유 글 답은 읽기(구조화 출력)로 값만 받고 코드가 저장합니다. 카드는 템플릿입니다."""
    reading = {
        "kind": "value",
        "facts": {
            "careers": [{"company_name": "OO물류", "start": "2012년 3월", "end": "2026년 9월"}]
        },
    }
    model = fake_agent_llm(
        [AIMessage("OO물류 경력을 적었어요.")],
        route="resume",
        structured=[{}, reading],  # 첫 턴("이력서 쓸게요")은 읽을 값 없음, 둘째 턴은 경력
    )
    headers = entered_headers("park")
    send(client, headers, "이력서 쓸게요")

    events = send(client, headers, "OO물류에서 2012년 3월부터 2026년 9월까지 일했어요")

    tokens = "".join(d["text"] for n, d in events if n == "token")
    assert tokens.strip() == "OO물류 경력을 적었어요."
    assert asked(events)["text"].startswith("OO물류에서 직급이나 직책이 있으셨어요?")
    assert asked(events)["question_id"] == "resume.career_position:c1"
    assert resume_data(client, headers)["careers"][0]["start_date"]["value"] == "2012-03"
    assert model.calls == 2  # 말하기만 셉니다(읽기는 구조화 출력)


def test_off_topic_goes_to_guide_and_keeps_the_question(client, entered_headers, fake_agent_llm):
    fake_agent_llm(
        [AIMessage("안내해 드릴게요.")], route="resume", structured=[{}, {"kind": "off_topic"}]
    )
    headers = entered_headers("park")
    first = asked(send(client, headers, "이력서 쓸게요"))

    events = send(client, headers, "실업급여는 언제부터 나와요?")

    assert not any(n == "ask_user" for n, _ in events)
    pending = client.get("/accounts/park", headers=headers).json()["pending_ask"]
    assert pending is None or pending["question_id"] == first["question_id"]


def test_entry_choice_reset_resume_is_an_action_run_by_code(
    client, entered_headers, fake_agent_llm
):
    """첫 안내 보기 "새로 쓸래요"는 코드가 이력서를 비우고, 모델은 새로 시작한다고만 말합니다."""
    fake_agent_llm([AIMessage("이력서를 비우고 새로 시작해요.")], route="resume")
    headers = entered_headers("choi")  # 예전 이력서가 있는 계정

    res = client.post("/accounts/choi/messages", headers=headers, json={"text": "새로 쓸래요"})
    events = sse_events(res)

    removed = [d for n, d in events if n == "form_update" and d["op"] == "remove"]
    assert removed, "예전 이력서 칸이 지워져야 합니다"
    assert client.get("/accounts/choi/resume", headers=headers).json()["data"]["careers"] == []
    assert asked(events)["question_id"] == "resume.career_new"


def test_no_previous_company_does_not_touch_certifications(client, entered_headers, fake_agent_llm):
    """ "그 전 회사" 질문의 "없어요"는 코드가 처리하고 자격증 칸은 건드리지 않습니다."""
    fake_agent_llm(
        [AIMessage("확인했어요.")],
        route="resume",
        # 모델로 넘어가면 "자격증 없음"으로 읽히게 두어, 버튼 답이 코드에서 잡히는지 봅니다.
        structured=[{}, {"kind": "value", "facts": {"no_certifications": True}}],
    )
    headers = entered_headers("park")
    fill(client, headers)
    assert (
        asked(send(client, headers, "경력은 다 말씀드렸어요"))["question_id"]
        == "resume.career_more"
    )

    events = send(client, headers, "없어요")

    assert asked(events)["question_id"] == "resume.license"
    assert resume_data(client, headers)["certifications_status"]["status"] != "not_applicable"
