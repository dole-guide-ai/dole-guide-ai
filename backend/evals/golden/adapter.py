"""골든셋 문항을 AI에 넣고 결과를 받는 자리. AI 본체가 붙으면 `run_agent` 하나만 채우면 됩니다.

채점은 grading.py가 AgentResult만 보고 합니다.
에이전트 내부 구조가 바뀌어도 이 함수만 맞추면 됩니다.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from evals.golden.grading import set_path


class AgentNotReadyError(RuntimeError):
    """AI 본체가 아직 연결되지 않았을 때. 해당 문항은 '건너뜀'으로 기록됩니다."""


@dataclass
class AgentResult:
    replies: list[str]  # 사용자 말 한 번마다 AI가 보인 답 문장
    next_action: str | None = None  # schema.NEXT_ACTIONS 중 하나
    # 결과 데이터. 경로 이름은 프론트 타입과 같습니다: derived(DerivedState)
    # · round(RoundCheckRead) · resume(ResumeValues) · activities(RoundActivity[])
    # · recognition(RecognitionFormRead)
    data: dict[str, Any] = field(default_factory=dict)
    cites: list[str] = field(default_factory=list)  # 근거 줄
    stored: list[str] = field(default_factory=list)  # DB 등에 저장된 값(데이터 밖에 저장한 것)
    # 모델에 보낸 글. 비우면 테스트가 gateway 호출을 자동으로 기록합니다.
    model_inputs: list[str] = field(default_factory=list)
    # 대화 전 데이터(변경금지 비교용). 실제 계정으로 돌리면 프리셋 시작 데이터와 달라 여기 담습니다.
    initial_data: dict[str, Any] | None = None


# 시연 seed에 있는 계정만 실제 그래프로 돌립니다. 가상 프리셋(general2 등)·상태값 덮어쓰기·활동 지정
# 문항은 계정 데이터를 그대로 만들 방법이 아직 없어 건너뜁니다(보고서에 '건너뜀'으로 남음).
SEED_PERSONAS = ("park", "choi", "lee")
# 절차 단계 → 다음 할 일 (schema.NEXT_ACTIONS)
NEXT_ACTION_BY_STAGE = {
    "job_registration": "write_resume",
    "education": "complete_education",
    "eligibility_application": "prepare_eligibility",
    "eligibility_applied": "enter_recognition_date",
    "recognition": "add_activity",
}
APPLICATION_PANEL_ACTION = "review_form"


def run_agent(case: dict[str, Any]) -> AgentResult:
    """문항 하나를 실제 AI로 실행합니다.

    case["input"]: persona, state(합친 상태값), data(시작 데이터),
    messages(턴별 말), files(첨부 이름).
    첨부 파일 경로는 schema.FILES_DIR / 이름. 그래프 호출은 서비스 함수(대화 턴)를 거칩니다.
    계정은 문항마다 새 방문자로 만들고 끝나면 지웁니다. 오늘 날짜는 프리셋의 demo_today입니다.
    """
    from app.core.config import get_settings
    from evals.golden.real import run_real

    settings = get_settings()
    if not (settings.has_llm_key() and settings.agent_model):
        raise AgentNotReadyError("모델 설정(AGENT_MODEL · 키)이 없어 실제 AI 평가를 건너뜀")
    _ensure_supported(case)
    return run_real(case)


def _ensure_supported(case: dict[str, Any]) -> None:
    from evals.golden.presets import BASE, LEE_ACTIVITIES, PERSONAS

    case_input = case["input"]
    persona = case_input["persona"]
    if persona not in SEED_PERSONAS:
        raise AgentNotReadyError(f"가상 프리셋 계정({persona})은 아직 실제 그래프로 못 돌려 건너뜀")
    if case_input["state"] != {**BASE, **PERSONAS[persona]}:
        raise AgentNotReadyError("상태값 덮어쓰기 문항은 아직 실제 그래프로 못 돌려 건너뜀")
    default = LEE_ACTIVITIES if persona == "lee" else []
    if case_input["activities"] != default:
        raise AgentNotReadyError("활동 지정 문항은 아직 실제 그래프로 못 돌려 건너뜀")


def run_selftest(case: dict[str, Any], broken: bool = False) -> AgentResult:
    """채점 코드 점검용 가짜 AI. selftest는 모든 기대를 맞추고, broken은 일부러 다 틀립니다."""
    expected = case["expected"]
    privacy = " ".join(item["text"] for item in expected["privacy"])
    if broken:
        return AgentResult(replies=[f"아무 답 {privacy}"], data={}, model_inputs=[privacy])
    data = deepcopy(case["input"]["data"])
    checks = sorted(expected["values"], key=lambda check: not check["path"].endswith(".length"))
    for check in checks:
        set_path(data, check["path"], _satisfying(check))
    reply = " ".join(expected["must_include"]) or "확인했어요."
    replies = [*["네."] * (len(case["input"]["messages"]) - 1), reply]
    return AgentResult(
        replies=replies,
        next_action=expected["next_action"],
        data=data,
        cites=["자체 점검 근거"] if expected["cite_required"] else [],
    )


def _satisfying(check: dict[str, Any]) -> Any:
    value = check["value"]
    if check["op"] == "ne":
        return f"{value}이(가) 아닌 값"
    if check["op"] in ("contains", "prefix"):
        return f"{value} (자체 점검)" if check["op"] == "contains" else f"{value}-01"
    return value
