"""도구 목록과 실행 (AI 설계 6.3·14장 2번 "도구 입출력 Pydantic 스키마").

각 도구는 (입력 모델, 실행 함수)이고, 실행 함수는 `ToolContext`와 검증된 입력을 받아
JSON으로 바꿀 수 있는
dict를 돌려줍니다. 서비스가 던진 `AppError`는 그대로 올라가 그래프가 사용자 안내로 바꿉니다.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.tools import guide
from app.schemas.activities import ActivityCreate, ActivityRoute
from app.schemas.common import FieldSource, FieldStatus, JsonPatchOp
from app.schemas.resume import FieldWrite
from app.services import activities as activity_service
from app.services import application as application_service
from app.services import imports as import_service
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
        if self.allowed_paths is not None and not path.startswith(self.allowed_paths):
            raise ToolError("지금 질문과 관계없는 칸이라 쓰지 않았어요.")


# ── 입력 모델 ─────────────────────────────────────────────


class NoInput(BaseModel):
    pass


class RecordActivityInput(BaseModel):
    """활동 하나 기록. 구분은 종류로 코드가 정합니다."""

    activity_date: date
    kind: str = Field(description="job_application·interview·lecture 등 활동 종류")
    route: ActivityRoute | None = None
    org_name: str | None = None
    job_title: str | None = None
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


class SaveResumeInput(BaseModel):
    fields: list[ResumeFieldInput] = Field(min_length=1, max_length=10)


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


# ── 실행 함수 ─────────────────────────────────────────────


def _dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")


def _check_round(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(round_service.read_current(ctx.db, ctx.account.user_id, ctx.today))


def _recommend(ctx: ToolContext, _: NoInput) -> dict[str, Any]:
    return _dump(recommendation_service.list_recommendations(ctx.db, ctx.account, ctx.today))


def _record_activity(ctx: ToolContext, args: RecordActivityInput) -> dict[str, Any]:
    body = ActivityCreate(**args.model_dump())
    result = activity_service.record_activity(
        ctx.db, ctx.account, body, ctx.today, source=FieldSource.USER_ANSWER
    )
    ctx.db.commit()
    return _dump(result)


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
            status=FieldStatus.CONFIRMED if f.confirmed else FieldStatus.EXTRACTED,
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
    )
}

# 패널(서브그래프)마다 LLM에 넘기는 도구 (AI 설계 6.3: 3~4개)
TOOLS_BY_PANEL: dict[str, tuple[str, ...]] = {
    "resume": ("save_resume_fields", "import_work24_items", "answer_overview"),
    "round": ("check_round", "record_activity", "mark_done", "recommend_activities"),
    "application": ("record_user_answer", "record_unsure", "check_round"),
    "education": ("search_trainings", "search_programs", "answer_overview"),
}


def run_tool(ctx: ToolContext, name: str, args: dict[str, Any]) -> dict[str, Any]:
    """이름과 인자로 도구를 실행합니다. 모르는 도구면 ToolError, 인자가 틀리면 ValidationError."""
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError("없는 도구예요.")
    return tool.run(ctx, tool.input_model.model_validate(args))
