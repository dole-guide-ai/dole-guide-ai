"""그래프가 주고받는 값의 모양입니다 (설계 초안 결정 ⑤: 정해진 칸으로 답 받기)."""

from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field

NextAction = Literal[
    "write_resume",
    "complete_education",
    "prepare_eligibility",
    "enter_recognition_date",
    "add_activity",
    "add_job_search_activity",
    "review_form",
    "submit_by_self",
]


class ActivityDraft(BaseModel):
    date: str
    kind: str | None = None
    route: str | None = None
    org_name: str | None = None
    job_title: str | None = None


class CareerDraft(BaseModel):
    company_name: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    position: str | None = None
    main_duties: str | None = None


class CertificationDraft(BaseModel):
    certificate_name: str
    acquired_date: str | None = None
    issuing_organization: str | None = None


class EducationDraft(BaseModel):
    school_name: str
    level: str | None = None
    graduation_status: str | None = None
    end_date: str | None = None


class AgentOutput(BaseModel):
    """모델이 돌려주는 JSON. 서류 값은 이번 말에서 새로 알게 된 것만 담습니다."""

    reply: str
    next_action: NextAction | None = None
    cites: list[str] = Field(default_factory=list)
    activities: list[ActivityDraft] = Field(default_factory=list)
    careers: list[CareerDraft] = Field(default_factory=list)
    certifications: list[CertificationDraft] = Field(default_factory=list)
    education: list[EducationDraft] = Field(default_factory=list)
    desired_occupations: list[str] = Field(default_factory=list)
    desired_regions: list[str] = Field(default_factory=list)


class Turn(TypedDict):
    role: Literal["user", "assistant"]
    text: str


class AgentState(TypedDict, total=False):
    """LangGraph 상태. 개인정보는 preprocess에서 가린 뒤에만 들어옵니다."""

    state: dict[str, Any]  # 절차 상태값 (프리셋·계정)
    data: dict[str, Any]  # resume · activities · recognition
    history: list[Turn]  # 지난 턴 (가린 글)
    message: str  # 이번 사용자 말 (가린 글)
    intent: str  # rule_question · report · other (classify_intent)
    situation: dict[str, Any]  # 규칙 코드가 계산한 derived · round
    output: AgentOutput
