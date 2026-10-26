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
from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.guard import check_input
from app.agent.tools import guide
from app.core.db import deferred_commit
from app.core.errors import ConflictError
from app.schemas.activities import ActivityCreate, ActivityRoute
from app.schemas.common import ErrorCode, FieldSource, FieldStatus, JsonPatchOp
from app.schemas.resume import FieldWrite
from app.services import activities as activity_service
from app.services import application as application_service
from app.services import imports as import_service
from app.services import knowledge as knowledge_service
from app.services import recommendations as recommendation_service
from app.services import resume as resume_service
from app.services import rounds as round_service
from app.services import trainings as training_service
from app.services import work24_codes
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
    # 대화 턴에서는 도구마다 저장점만 확정하고 commit은 턴 끝에 한 번 합니다
    # (core/db.deferred_commit).
    defer_commit: bool = False

    def ensure_allowed(self, path: str) -> None:
        if self.allowed_paths is not None and not any(
            path == p or path.startswith(p.rstrip("/") + "/") for p in self.allowed_paths
        ):
            raise ToolError("지금 질문과 관계없는 칸이라 쓰지 않았어요.")


# ── 입력 모델 ─────────────────────────────────────────────


class NoInput(BaseModel):
    pass


class RecordActivityInput(BaseModel):
    """활동 하나 기록. 구분은 종류로 코드가 정합니다."""

    activity_date: date = Field(description="활동한 날 YYYY-MM-DD (오늘 날짜 기준으로 바꿈)")
    kind: str = Field(
        description="활동 종류: job_application(입사지원) · interview(면접) · lecture(취업특강) · "
        "training(직업훈련) · aptitude_test(직업심리검사) · counseling · volunteer 등"
    )
    route: ActivityRoute | None = Field(
        default=None,
        description="경로: work24(고용24·워크넷) · portal(사람인 같은 취업포털) · "
        "company_site(회사 홈페이지) · email · interview(면접) · visit · mail · fax · "
        "referral(지인 소개) · job_fair(채용행사) · newspaper · step_online · training",
    )
    org_name: str | None = Field(default=None, description="회사·기관 이름(사람 이름 아님)")
    job_title: str | None = Field(default=None, description="지원한 직무(예: 사무보조)")
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
    # "없어요"라고 답한 섹션(자격면허·그 밖의 역량). 값 없이 해당 없음으로 둡니다.
    not_applicable: bool = False


class SaveResumeInput(BaseModel):
    fields: list[ResumeFieldInput] = Field(min_length=1, max_length=10)


class ConfirmFieldInput(BaseModel):
    path: str = Field(pattern=r"^/", description="확인받은 이력서 칸 경로")


class UserAnswerInput(BaseModel):
    path: str = Field(pattern=r"^/", description="/work/has_work 같은 본인 답변 칸")
    value: Any


class UnsureInput(BaseModel):
    path: str = Field(pattern=r"^/")


class ImportInput(BaseModel):
    import_ids: list[str] = Field(min_length=1, max_length=20)


class SearchTrainingsInput(BaseModel):
    keyword: str | None = None
    region: str | None = None


class SearchProgramsInput(BaseModel):
    start: date | None = None


class SearchGuideInput(BaseModel):
    query: str = Field(min_length=2, max_length=200, description="규칙·절차·제도 질문")


class LookupCodeInput(BaseModel):
    kind: Literal["occupation", "region"] = Field(description="occupation 직종, region 지역")
    text: str = Field(min_length=1, max_length=50, description="사용자가 말한 직종·지역 이름")


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


# 경로를 말하지 않아도 종류로 정해지는 경우 (면접은 경로도 면접)
_ROUTE_BY_KIND = {"interview": ActivityRoute.INTERVIEW, "training": ActivityRoute.TRAINING}


def _record_activity(ctx: ToolContext, args: RecordActivityInput) -> dict[str, Any]:
    values = args.model_dump()
    if values["route"] is None:
        values["route"] = _ROUTE_BY_KIND.get(args.kind)
    body = ActivityCreate(**values)
    try:
        updates = activity_service.record_answered_activity(ctx.db, ctx.account, body, ctx.today)
    except ConflictError as exc:
        if exc.code != ErrorCode.ROUND_CLOSED:
            raise
        check = round_service.read_current(ctx.db, ctx.account.user_id, ctx.today)
        raise ToolError(
            f"이번 회차 대상기간({check.period_start} ~ {check.period_end}) 밖 날짜라 이번 회차 "
            "활동으로 기록하지 않았어요."
        ) from None
    return _dump(updates)


def _mark_done(ctx: ToolContext, args: MarkDoneInput) -> dict[str, Any]:
    return _dump(
        recommendation_service.mark_done(
            ctx.db, ctx.account, args.activity_id, args.done_on, ctx.today, args.org_name
        )
    )


def _write_status(f: ResumeFieldInput) -> FieldStatus:
    if f.not_applicable:
        return FieldStatus.NOT_APPLICABLE
    return FieldStatus.CONFIRMED if f.confirmed else FieldStatus.EXTRACTED


def _save_resume(ctx: ToolContext, args: SaveResumeInput) -> dict[str, Any]:
    for f in args.fields:
        ctx.ensure_allowed(f.path)
    writes = [
        FieldWrite(
            path=f.path,
            value=f.value,
            status=_write_status(f),
            source=FieldSource.USER_ANSWER,
        )
        for f in args.fields
    ]
    result = resume_service.save_resume_fields(ctx.db, ctx.account.user_id, writes, today=ctx.today)
    return {
        "updates": [_dump(u) for u in result.updates],
        "next_question": _dump(result.next_question),
        "issues": [_dump(i) for i in result.issues],
    }


def _confirm_resume(ctx: ToolContext, args: ConfirmFieldInput) -> dict[str, Any]:
    ctx.ensure_allowed(args.path)
    result = resume_service.confirm_field(ctx.db, ctx.account.user_id, args.path, today=ctx.today)
    return {
        "updates": [_dump(u) for u in result.updates],
        "next_question": _dump(result.next_question),
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


def _search_guide(ctx: ToolContext, args: SearchGuideInput) -> dict[str, Any]:
    """RAG 근거 검색. 지시가 숨어 있는 자료는 빼고(간접 주입 방지), 없으면 not_found."""
    chunks = [
        c
        for c in knowledge_service.search(ctx.db, args.query)
        if not check_input(c["text"]).blocked
    ]
    return {"chunks": chunks, "not_found": not chunks}


def _lookup_code(ctx: ToolContext, args: LookupCodeInput) -> dict[str, Any]:
    """고용24 공통코드 후보 3개. 저장된 기준표(JSON)에서 찾고 API는 부르지 않습니다."""
    candidates = work24_codes.lookup_code(args.kind, args.text)
    return {
        "candidates": [_dump(c) for c in candidates],
        # 후보가 다 맞지 않으면 이 값으로 이름만 저장합니다(세 번 실패하면, F-14).
        "name_only": work24_codes.name_only(args.text),
    }


def _overview(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return guide.overview()


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
        Tool("check_round", "이번 회차 점검(인정 건수·부족·경고·필요 증빙)", NoInput, _check_round),
        Tool("recommend_activities", "부족한 활동 추천 최대 3개", NoInput, _recommend),
        Tool(
            "record_activity",
            "활동 기록",
            RecordActivityInput,
            _record_activity,
        ),
        Tool("mark_done", "예정 활동을 했어요로 바꾸기", MarkDoneInput, _mark_done),
        Tool(
            "save_resume_fields",
            "이력서 칸 쓰기",
            SaveResumeInput,
            _save_resume,
        ),
        Tool(
            "confirm_resume_field",
            "확인 질문에 맞다고 한 이력서 칸 확정",
            ConfirmFieldInput,
            _confirm_resume,
        ),
        Tool("record_user_answer", "신청서 본인 답변 한 칸 저장", UserAnswerInput, _record_answer),
        Tool("record_unsure", "확인 필요로 두기", UnsureInput, _record_unsure),
        Tool("import_work24_items", "고용24 불러오기에서 고른 항목 넣기", ImportInput, _import),
        Tool("search_trainings", "훈련과정 찾기", SearchTrainingsInput, _trainings),
        Tool(
            "search_programs",
            "센터 특강 일정",
            SearchProgramsInput,
            _programs,
        ),
        Tool("answer_overview", "전체 순서 4단계 고정 안내(LLM 없이)", NoInput, _overview),
        Tool(
            "search_guide",
            "실업급여 규칙·절차·제도를 고용24 정책·1350 FAQ에서 찾기 (근거 줄)",
            SearchGuideInput,
            _search_guide,
        ),
        Tool(
            "lookup_code",
            "말한 직종·지역 이름으로 고용24 공통코드 후보 3개 찾기",
            LookupCodeInput,
            _lookup_code,
        ),
    )
}

# 패널(서브그래프)마다 LLM에 넘기는 도구 (AI 설계 6.3: 3~4개)
TOOLS_BY_PANEL: dict[str, tuple[str, ...]] = {
    "resume": (
        "save_resume_fields",
        "confirm_resume_field",
        "lookup_code",
        "import_work24_items",
    ),
    "round": ("check_round", "record_activity", "mark_done", "recommend_activities"),
    "application": ("record_user_answer", "record_unsure", "check_round"),
    "education": ("search_trainings", "search_programs", "answer_overview"),
}


def execute(ctx: ToolContext, tool: Tool, args: BaseModel) -> dict[str, Any]:
    """도구 하나를 실행합니다. 대화 턴이면 저장점 하나로 묶습니다."""
    if not ctx.defer_commit:
        return tool.run(ctx, args)
    with deferred_commit(ctx.db):
        return tool.run(ctx, args)


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """이름과 인자로 도구를 실행합니다. 모르는 도구면 ToolError, 인자가 틀리면 ValidationError."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError("없는 도구예요.")
    return execute(ctx, tool, tool.input_model.model_validate(args))
