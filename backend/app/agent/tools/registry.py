"""도구 목록과 실행 (AI 설계 6.3·14장 2번 "도구 입출력 Pydantic 스키마").

각 도구는 (입력 모델, 실행 함수)이고, 실행 함수는 `ToolContext`와 검증된 입력을 받아
JSON으로 바꿀 수 있는
dict를 돌려줍니다. 서비스가 던진 `AppError`는 그대로 올라가 그래프가 사용자 안내로 바꿉니다.
"""

import dataclasses
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.input import pii
from app.core.errors import AppError
from app.rules import rounds as rounds_rules
from app.rules.days import normalize_day
from app.schemas.activities import ActivityCreate, ActivityRoute
from app.schemas.common import JsonPatchOp
from app.services import activities as activity_service
from app.services import application as application_service
from app.services import imports as import_service
from app.services import knowledge as knowledge_service
from app.services import procedure as procedure_service
from app.services import recommendations as recommendation_service
from app.services import rounds as round_service
from app.services import trainings as training_service
from app.services.accounts import AccountContext

CURRENT_ROUND = "current"


# 교육 이수 칸(절차 PATCH 경로). 절차 날짜·단계는 도구로 쓰지 않고 이 칸 하나만 씁니다.
EDUCATION_DONE_PATH = "/education_done"


class ToolError(Exception):
    """도구를 부를 수 없는 경우(권한 밖 칸 등). 메시지는 LLM에게 거절 사유로 돌려줍니다."""


PRIVATE_VALUE_MESSAGE = (
    "개인정보나 건강·다툼·종교 같은 사정이 든 값은 저장하지 않아요. 그 부분은 빼고 저장하세요."
)


@dataclass
class ToolContext:
    """도구가 쓰는 계정·날짜. LLM이 정하지 않고 그래프 상태에서 넣습니다."""

    db: Session
    account: AccountContext
    today: date
    now: datetime
    # 지금 질문이 다루는 칸 경로(앞부분). None이면 제한 없음(테스트·관리용)
    allowed_paths: tuple[str, ...] | None = None
    # 이번 턴에 올린 구직활동 증빙 파일. 이 턴에 처음 기록하는 활동에 붙입니다(take_evidence).
    evidence_file_ids: list[str] = field(default_factory=list)

    def take_evidence(self) -> list[str]:
        """증빙을 한 번만 내줍니다. 사진 한 장은 보통 활동 하나의 증빙이라 두 번째부터는 빈 목록."""
        taken, self.evidence_file_ids = self.evidence_file_ids, []
        return taken

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
    done: bool = Field(
        True,
        description=(
            "사용자가 이미 한 활동이면 true, 앞으로 할 예정이면 false. "
            "요일·날짜만 말했을 때 지난 날인지 다가올 날인지를 이 값으로 정합니다"
        ),
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


class AttachEvidenceInput(BaseModel):
    activity_id: uuid.UUID = Field(description="check_round activities에 있는 기존 활동 ID")


class EditActivityInput(BaseModel):
    """이미 기록한 활동 하나를 고치거나 지웁니다. 사용자가 잘못 말한 것을 바로잡을 때만 씁니다."""

    activity_id: uuid.UUID = Field(description="check_round 결과 activities의 activity_id")
    remove: bool = Field(False, description="활동을 지우려면 true")
    when: str | None = Field(None, description="바로잡은 날짜 표현 그대로(예: 어제, 12월 15일)")
    done: bool = Field(True, description="이미 한 활동이면 true, 앞으로 할 예정이면 false")
    kind: str | None = None
    route: ActivityRoute | None = None
    org_name: str | None = Field(None, description="회사·기관 이름만")
    job_title: str | None = None


class MarkDoneInput(BaseModel):
    activity_id: uuid.UUID
    done_on: date
    org_name: str | None = None


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


def _complete_education(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    """교육 이수만 표시합니다(화면의 '교육 다 들었어요'와 같은 서비스). 교육 단계가 아니면 409."""
    patch = [JsonPatchOp(op="replace", path=EDUCATION_DONE_PATH, value=True)]
    return _dump(procedure_service.patch_procedure(ctx.db, ctx.account, patch, ctx.now))


def _check_round(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(round_service.read_current(ctx.db, ctx.account.user_id, ctx.today))


def _recommend(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(recommendation_service.list_recommendations(ctx.db, ctx.account, ctx.now))


def _record_activity(ctx: ToolContext, args: RecordActivityInput) -> dict[str, Any]:
    day = _day(ctx, args.when, args.done)
    # 이번 회차에 인정되지 않는 종류(반복수급자 3차부터 특강 등)·한도를 넘은 활동은 넣지 않고
    # 이유를 돌려줍니다. 회차 계산과 같은 규칙 함수(rules/rounds.admission)로 봅니다.
    if (verdict := _admission(ctx, args.kind)) is not None:
        return {"recorded": False, "admission": dataclasses.asdict(verdict)}
    body = ActivityCreate(
        activity_date=day,
        file_ids=list(ctx.evidence_file_ids),
        **args.model_dump(exclude={"when", "done"}),
    )
    # 아직 하지 않은 일은 오늘 날짜여도 예정으로 둡니다(인정 건수에 넣지 않음).
    recorded = activity_service.record_answered_activity(
        ctx.db, ctx.account, body, ctx.today, planned=not args.done
    )
    # 기록이 실패하면 증빙을 남겨 두어 모델이 다시 부를 때 그대로 붙습니다.
    ctx.take_evidence()
    return {
        **_dump(recorded),
        "recorded": True,
        "activity_date": day.isoformat(),
        "planned": not args.done or day > ctx.today,
    }


def _day(ctx: ToolContext, when: str, done: bool) -> date:
    """사용자가 말한 날짜 표현 → 날짜(rules/days). 정하지 못하면 다시 묻게 합니다."""
    day = normalize_day(when, ctx.today, done=done)
    if day is None:
        raise ToolError(f"'{when}'이(가) 며칠인지 정하지 못했어요. 날짜를 다시 물어 주세요.")
    return day


def _admission(ctx: ToolContext, kind: str) -> rounds_rules.Admission | None:
    """인정되지 않는 활동이면 그 판정, 인정되거나 지금 회차가 없으면 None."""
    try:
        current = round_service.evaluate(ctx.db, ctx.account.user_id, ctx.today)
    except AppError:  # 지금 회차가 없음: 기록 서비스가 같은 이유로 거절합니다
        return None
    verdict = rounds_rules.admission(
        kind, current.group, current.target.round_no, current.result.limits_used
    )
    return verdict if verdict.status is not None else None


def _attach_evidence(ctx: ToolContext, args: AttachEvidenceInput) -> dict[str, Any]:
    if not ctx.evidence_file_ids:
        raise ToolError("이번에 올린 증빙 파일이 없어요.")
    patch = [
        JsonPatchOp(op="add", path=f"{activity_service.FILE_IDS_PATH}/-", value=file_id)
        for file_id in ctx.evidence_file_ids
    ]
    updated = activity_service.patch_activity(
        ctx.db, ctx.account, str(args.activity_id), patch, ctx.today
    )
    # 붙이기가 실패하면 증빙을 남겨 두어 record_activity로 새로 기록할 때 붙습니다.
    ctx.take_evidence()
    return _dump(updated)


def _edit_activity(ctx: ToolContext, args: EditActivityInput) -> dict[str, Any]:
    activity_id = str(args.activity_id)
    if args.remove:
        return _dump(activity_service.delete_activity(ctx.db, ctx.account, activity_id, ctx.today))
    values: dict[str, Any] = args.model_dump(include={"kind", "route", "org_name", "job_title"})
    if args.when is not None:
        values["activity_date"] = _day(ctx, args.when, args.done).isoformat()
    patch = [
        JsonPatchOp(op="replace", path=f"/{field}", value=value)
        for field, value in values.items()
        if value is not None
    ]
    if not patch:
        raise ToolError("고칠 값이 없어요. 무엇을 바로잡을지 다시 물어 주세요.")
    return _dump(
        activity_service.patch_activity(ctx.db, ctx.account, activity_id, patch, ctx.today)
    )


def _mark_done(ctx: ToolContext, args: MarkDoneInput) -> dict[str, Any]:
    return _dump(
        recommendation_service.mark_done(
            ctx.db, ctx.account, args.activity_id, args.done_on, ctx.today, args.org_name
        )
    )


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
    # 서류·활동에 값을 저장하는 도구. 저장할 값에 가린 개인정보·민감한 사정이 있으면 막습니다.
    writes: bool = False


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
            writes=True,
        ),
        Tool(
            "attach_evidence",
            "이번 턴에 올린 증빙 사진·문서를 이미 기록된 활동 하나에 붙임",
            AttachEvidenceInput,
            _attach_evidence,
            writes=True,
        ),
        Tool(
            "mark_done",
            "추천받아 예정으로 둔 활동을 사용자가 실제로 했다고 할 때 완료로 바꿈",
            MarkDoneInput,
            _mark_done,
            writes=True,
        ),
        Tool(
            "record_user_answer",
            "실업인정 신청서에서 본인만 답할 수 있는 칸(근로·소득·취업 여부 등) 하나를 저장. "
            "이력서에는 쓰지 않음",
            UserAnswerInput,
            _record_answer,
            writes=True,
        ),
        Tool(
            "record_unsure",
            "실업인정 신청서 칸에 사용자가 모르겠다고 답했을 때 그 칸을 확인 필요로 둠",
            UnsureInput,
            _record_unsure,
            writes=True,
        ),
        Tool(
            "complete_education",
            "수급자격 신청자 교육을 다 들었다고 사용자가 말하면 교육 이수로 표시하고 다음 단계로 "
            "넘김. 교육 단계에서만 되고, 듣지 않았으면 쓰지 않음",
            NoInput,
            _complete_education,
            writes=True,
        ),
        Tool(
            "edit_activity",
            "이미 기록한 활동 하나의 날짜·회사·종류를 바로잡거나 지움. 사용자가 잘못 말했다고 "
            "정정할 때만 쓰고, 사실과 다르게 바꾸는 요청에는 쓰지 않음",
            EditActivityInput,
            _edit_activity,
            writes=True,
        ),
        Tool(
            "import_work24_items",
            "고용24 불러오기에서 고른 항목 넣기",
            ImportInput,
            _import,
            writes=True,
        ),
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
# 최대 5개로 조정. 이미 기록된 활동에 증빙을 붙이는 attach_evidence를 더하며 6개. 도구가 많을수록
# 선택이 흔들려서(1단계 실험) 늘릴 때는 골든셋으로 다시 잽니다)
# 기록한 활동 바로잡기·지우기(edit_activity)를 하나로 더해 7개(inject 모드는 lookup_rules를 빼 6개).
MAX_PANEL_TOOLS = 7
TOOLS_BY_PANEL: dict[str, tuple[str, ...]] = {
    # 이력서 칸 저장은 도구가 아니라 읽기·말하기 노드가 합니다(nodes/resume)
    "resume": ("import_work24_items",),
    "round": (
        "check_round",
        "record_activity",
        "attach_evidence",
        "edit_activity",
        "mark_done",
        "recommend_activities",
        "lookup_rules",
    ),
    "application": ("record_user_answer", "record_unsure", "check_round", "lookup_rules"),
    "guide": ("lookup_rules", "search_trainings", "search_programs", "complete_education"),
}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """이름과 인자로 도구를 실행합니다. 모르는 도구면 ToolError, 인자가 틀리면 ValidationError."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError("없는 도구예요.")
    if tool.writes and pii.carries_private(args):
        raise ToolError(PRIVATE_VALUE_MESSAGE)
    return tool.run(ctx, tool.input_model.model_validate(args))
