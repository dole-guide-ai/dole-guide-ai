"""이력서 인터뷰 평가: 가상 사용자와 여러 턴 대화해 에이전트가 이력서를 이끌어 채우는지 봅니다.

실행: backend/에서 `uv run pytest evals/test_interview.py -m eval -q`
보고서: evals/reports/interview-<시각>.md (모든 시나리오가 끝난 뒤 한 파일)
"""

import pytest

from evals.interview.driver import AgentDriver
from evals.interview.report import InterviewReport, Run
from evals.interview.scenarios import SCENARIOS, Scenario
from evals.interview.scoring import score_dialogue, score_resume
from evals.interview.simulator import END, next_user_message

pytestmark = pytest.mark.eval
# 사용자 말 수 상한. 이력서 필수 칸(경력·학력·자격·희망)을 묻기에 넉넉한 수
MAX_TURNS = 16


@pytest.fixture(scope="module")
def interview_report():
    report = InterviewReport()
    yield report
    if report.runs:
        print(f"\n이력서 인터뷰 보고서: {report.write()}")


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_interview(scenario: Scenario, db_session, requires_llm, interview_report) -> None:
    agent = AgentDriver(db_session, scenario.id)
    transcript: list[tuple[str, str]] = []
    message, ended = scenario.opening, False
    for _ in range(MAX_TURNS):
        transcript.append((message, agent.send(message)))
        message = next_user_message(scenario, transcript)
        if END in message:
            ended = True
            break
    score = score_dialogue(
        score_resume(scenario, agent.resume()), [a for _, a in transcript], ended
    )
    interview_report.runs.append(Run(scenario.id, scenario.title, score, transcript))
