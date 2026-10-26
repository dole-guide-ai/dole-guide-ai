"""도구 목록과 실행 (AI 설계 6.3·14장 2번 "도구 입출력 Pydantic 스키마").

각 도구는 (입력 모델, 실행 함수)이고, 실행 함수는 `ToolContext`와 검증된 입력을 받아
JSON으로 바꿀 수 있는
dict를 돌려줍니다. 서비스가 던진 `AppError`는 그대로 올라가 그래프가 사용자 안내로 바꿉니다.
"""

import dataclasses
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.rules.days import normalize_day
from app.rules.resume_facts import ResumeFacts, plan_writes
from app.schemas.activities import ActivityCreate, ActivityRoute
from app.schemas.common import FieldSource, FieldStatus, JsonPatchOp
from app.schemas.resume import FieldWrite
from app.services import accounts as account_service
from app.services import activities as activity_service
from app.services import application as application_service
from app.services import imports as import_service
from app.services import knowledge as knowledge_service
from app.services import recommendations as recommendation_service
from app.services import resume as resume_service
from app.services import rounds as round_service
from app.services import trainings as training_service
from app.services.accounts import AccountContext

CURRENT_ROUND = "current"


class ToolError(Exception):
    """도구를 부를 수 없는 경우(권한 밖 칸 등). 메시지는 LLM에게 거절 사유로 돌려줍니다."""


@dataclass
class ToolContext:
    """도구가 쓰는 계정·날짜. LLM이 정하지 않고 그래프 상태에서 넣습니다."""

    db: Session
    account: AccountContext
    today: date
    now: datetime
    # 지금 질문이 다루는 칸 경로(앞부분). None이면 제한 없음(테스트·관리용)
    allowed_paths: tuple[str, ...] | None = None

    def ensure_allowed(self, path: str) -> None:
        if self.allowed_paths is not None and not any(
            path == p or path.startswith(p.rstrip("/") + "/") for p in self.allowed_paths
        ):
            raise ToolError("지금 질문과 관계없는 칸이라 쓰지 않았어요.")


# ── 입력 모델 ─────────────────────────────────────────────


class NoInput(BaseModel):
    pass


class RecordActivityInput(BaseModel):
    """활동 하나 기록. 구분은 종류로, 날짜는 말한 표현으로 코드가 정합니다."""

    when: str = Field(
        description="사용자가 말한 날짜 표현 그대로(예: 어제, 지난주 금요일, 11월 20일)"
    )
    kind: str = Field(description="job_application·interview·lecture 등 활동 종류")
    route: ActivityRoute | None = None
    org_name: str | None = Field(
        None,
        description=(
            "회사·기관 이름만(예: OO기획). 공고 제목의 '채용'·'모집'·'공고'·직무명은 빼고, "
            "직무는 job_title에"
        ),
    )
    job_title: str | None = Field(None, description="지원한 직무(예: 경리, 지게차 운전)")
    hours: float | None = None


class MarkDoneInput(BaseModel):
    activity_id: uuid.UUID
    done_on: date
    org_name: str | None = None


class ResumeFieldInput(BaseModel):
    path: str = Field(pattern=r"^/", description="/careers/c1/company_name 같은 칸 경로")
    value: Any = None
    # 사용자가 말한 값을 그대로 넣었는지(extracted), 다시 확인받았는지(confirmed)
    confirmed: bool = False
    # 섹션을 "없어요"로 둘 때(예: /competencies_status). value는 비웁니다.
    not_applicable: bool = False


class SaveResumeInput(BaseModel):
    fields: list[ResumeFieldInput] = Field(min_length=1, max_length=10)


class UserAnswerInput(BaseModel):
    path: str = Field(pattern=r"^/", description="/work/has_work 같은 본인 답변 칸")
    value: Any


class UnsureInput(BaseModel):
    path: str = Field(pattern=r"^/")


class ImportInput(BaseModel):
    import_ids: list[str] = Field(min_length=1, max_length=20)


class LookupRulesInput(BaseModel):
    query: str = Field(
        description="찾을 규칙 주제를 짧게(예: 이메일 지원 증빙, 신청 마감 시간, 일용직 자격)"
    )


class SearchTrainingsInput(BaseModel):
    keyword: str | None = None
    region: str | None = None


class SearchProgramsInput(BaseModel):
    start: date | None = None


# ── 실행 함수 ─────────────────────────────────────────────


def _dump(model: Any) -> dict[str, Any]:
    """Pydantic 모델이나 규칙 dataclass를 JSON으로 바꿀 수 있는 dict로."""
    if dataclasses.is_dataclass(model):
        return json.loads(json.dumps(dataclasses.asdict(model), default=str))
    return model.model_dump(mode="json")


def _check_round(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(round_service.read_current(ctx.db, ctx.account.user_id, ctx.today))


def _recommend(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(recommendation_service.list_recommendations(ctx.db, ctx.account, ctx.today))


def _record_activity(ctx: ToolContext, args: RecordActivityInput) -> dict[str, Any]:
    day = normalize_day(args.when, ctx.today)
    if day is None:
        raise ToolError(f"'{args.when}'이(가) 며칠인지 정하지 못했어요. 날짜를 다시 물어 주세요.")
    body = ActivityCreate(activity_date=day, **args.model_dump(exclude={"when"}))
    return _dump(activity_service.record_answered_activity(ctx.db, ctx.account, body, ctx.today))


def _record_resume_facts(ctx: ToolContext, args: ResumeFacts) -> dict[str, Any]:
    procedure = account_service.read_procedure(ctx.db, ctx.account.user_id)
    current = resume_service.read_resume(ctx.db, ctx.account).data
    plan = plan_writes(current, args, ctx.today, procedure.separation_date)
    result: dict[str, Any] = {"saved": 0, "ask": plan.asks}
    if plan.writes:
        saved = resume_service.save_resume_fields(
            ctx.db, ctx.account.user_id, plan.writes, today=ctx.today
        )
        result.update(
            saved=len(plan.writes),
            updates=[_dump(u) for u in saved.updates],
            issues=[_dump(i) for i in saved.issues],
        )
    return result


def _mark_done(ctx: ToolContext, args: MarkDoneInput) -> dict[str, Any]:
    return _dump(
        recommendation_service.mark_done(
            ctx.db, ctx.account, args.activity_id, args.done_on, ctx.today, args.org_name
        )
    )


def _save_resume(ctx: ToolContext, args: SaveResumeInput) -> dict[str, Any]:
    for f in args.fields:
        ctx.ensure_allowed(f.path)
    writes = [
        FieldWrite(
            path=f.path,
            value=f.value,
            status=(
                FieldStatus.NOT_APPLICABLE
                if f.not_applicable
                else FieldStatus.CONFIRMED
                if f.confirmed
                else FieldStatus.EXTRACTED
            ),
            source=FieldSource.USER_ANSWER,
        )
        for f in args.fields
    ]
    result = resume_service.save_resume_fields(ctx.db, ctx.account.user_id, writes, today=ctx.today)
    return {
        "updates": [_dump(u) for u in result.updates],
        "issues": [_dump(i) for i in result.issues],
    }


def _record_answer(ctx: ToolContext, args: UserAnswerInput) -> dict[str, Any]:
    ctx.ensure_allowed(args.path)
    op = JsonPatchOp(op="replace", path=args.path, value=args.value)
    updates = application_service.record_user_answer(
        ctx.db, ctx.account, CURRENT_ROUND, [op], ctx.now
    )
    return {"updates": [_dump(u) for u in updates]}


def _record_unsure(ctx: ToolContext, args: UnsureInput) -> dict[str, Any]:
    ctx.ensure_allowed(args.path)
    updates = application_service.record_unsure(
        ctx.db, ctx.account, CURRENT_ROUND, args.path, ctx.now
    )
    return {"updates": [_dump(u) for u in updates]}


def _import(ctx: ToolContext, args: ImportInput) -> dict[str, Any]:
    return _dump(import_service.apply_imports(ctx.db, ctx.account, args.import_ids, ctx.today))


def _trainings(ctx: ToolContext, args: SearchTrainingsInput) -> dict[str, Any]:
    keyword = args.keyword or training_service.desired_occupation(ctx.db, ctx.account.user_id)
    return _dump(training_service.search_trainings(keyword, args.region, ctx.today, ctx.now))


def _programs(ctx: ToolContext, args: SearchProgramsInput) -> dict[str, Any]:
    return _dump(training_service.search_programs(args.start, ctx.now))


# 한 번에 돌려주는 규칙 카드 수. 많을수록 엉뚱한 카드가 섞여 답을 흐립니다.
LOOKUP_LIMIT = 3


def _lookup_rules(ctx: ToolContext, args: LookupRulesInput) -> dict[str, Any]:
    found = knowledge_service.search(ctx.db, args.query, LOOKUP_LIMIT, guide_limit=0)
    return {"rules": [c.for_model() for c in knowledge_service.rule_cards_of(found.rules)]}


# ── 목록 ─────────────────────────────────────────────


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_model: type[BaseModel]
    run: Callable[[ToolContext, Any], dict[str, Any]]


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in (
        Tool(
            "check_round",
            "이번 실업인정 회차의 필요 건수·인정 건수·부족 건수·경고·필요 증빙을 계산해 돌려줌",
            NoInput,
            _check_round,
        ),
        Tool(
            "recommend_activities",
            "이번 회차에 부족한 재취업활동을 할 수 있는 활동으로 최대 3개 추천",
            NoInput,
            _recommend,
        ),
        Tool(
            "record_activity",
            "사용자가 실제로 한 재취업활동(입사지원·면접 등) 하나를 이번 회차 활동으로 기록",
            RecordActivityInput,
            _record_activity,
        ),
        Tool(
            "mark_done",
            "추천받아 예정으로 둔 활동을 사용자가 실제로 했다고 할 때 완료로 바꿈",
            MarkDoneInput,
            _mark_done,
        ),
        Tool(
            "record_resume_facts",
            "사용자가 말한 이력서 사실(경력·학력·자격증·희망 직종·지역)을 이력서에 저장. "
            "말한 값과 날짜 표현만 넣으면 칸·날짜 변환은 서버가 함",
            ResumeFacts,
            _record_resume_facts,
        ),
        Tool(
            "save_resume_fields",
            "이력서 칸 경로로 값 쓰기. record_resume_facts에 없는 칸(제목·희망 월급·고용형태·"
            "병역·근무시간·그 밖의 역량·운전·경력 월급 등)과 섹션 '없음'(not_applicable)",
            SaveResumeInput,
            _save_resume,
        ),
        Tool(
            "record_user_answer",
            "실업인정 신청서에서 본인만 답할 수 있는 칸(근로·소득·취업 여부 등) 하나를 저장. "
            "이력서에는 쓰지 않음",
            UserAnswerInput,
            _record_answer,
        ),
        Tool(
            "record_unsure",
            "실업인정 신청서 칸에 사용자가 모르겠다고 답했을 때 그 칸을 확인 필요로 둠",
            UnsureInput,
            _record_unsure,
        ),
        Tool("import_work24_items", "고용24 불러오기에서 고른 항목 넣기", ImportInput, _import),
        Tool("search_trainings", "훈련과정 찾기", SearchTrainingsInput, _trainings),
        Tool(
            "search_programs",
            "센터 특강 일정",
            SearchProgramsInput,
            _programs,
        ),
        Tool(
            "lookup_rules",
            "팀 규칙표에서 실업급여 규칙(증빙·마감·인정 여부·횟수·예외)을 찾아 "
            "내용과 출처를 돌려줌. 규칙 질문은 기억으로 답하지 말고 먼저 이 도구로 찾음",
            LookupRulesInput,
            _lookup_rules,
        ),
    )
}

# 패널마다 LLM에 넘기는 도구 (AI 설계 6.3: 3~4개였으나 4단계에서 규칙 찾기 lookup_rules를 더하며
# 최대 5개로 조정. 도구가 많을수록 선택이 흔들려서(1단계 실험) 늘릴 때는 골든셋으로 다시 잽니다)
MAX_PANEL_TOOLS = 5
TOOLS_BY_PANEL: dict[str, tuple[str, ...]] = {
    # 사실 추출(경력·학력 날짜 변환)은 record_resume_facts, 그 밖의 모든 칸은 save_resume_fields
    "resume": ("record_resume_facts", "save_resume_fields", "import_work24_items"),
    "round": (
        "check_round",
        "record_activity",
        "mark_done",
        "recommend_activities",
        "lookup_rules",
    ),
    "application": ("record_user_answer", "record_unsure", "check_round", "lookup_rules"),
    "guide": ("lookup_rules", "search_trainings", "search_programs"),
}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """이름과 인자로 도구를 실행합니다. 모르는 도구면 ToolError, 인자가 틀리면 ValidationError."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError("없는 도구예요.")
    return tool.run(ctx, tool.input_model.model_validate(args))
