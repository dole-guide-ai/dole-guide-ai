"""회차 점검 (F-18, 상세기획 2-2.6). 활동을 읽어 규칙 함수 `check_round`로 계산합니다.

계산 결과는 저장하지 않고 매번 다시 계산합니다(설계 원칙: 계산 값은 저장 안 함).
활동 기록·빼기(F-17·F-20)와 추천(F-19)·신청서(F-23)가 같은 결과를 씁니다.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models import Activity, Round
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.rules import periods
from app.rules.application import ActivityInput
from app.rules.rounds import RoundResult, check_round
from app.schemas.common import ErrorCode, FormName, FormUpdate
from app.schemas.rounds import RoundCheck
from app.services import accounts as account_service

DEFAULT_GROUP = "general"


@dataclass
class RoundContext:
    """지금 회차와 그 계산 결과. 활동 기록·추천이 함께 씁니다."""

    target: Round
    rounds: list[Round]
    group: str
    inputs: list[ActivityInput]
    result: RoundResult


def to_inputs(db: Session, activities: list[Activity]) -> list[ActivityInput]:
    evidence = activity_repo.file_ids_by_activity(db, [a.activity_id for a in activities])
    return [
        ActivityInput(
            activity_id=str(a.activity_id),
            activity_date=a.activity_date,
            category=a.category,
            kind=a.kind,
            route=a.route,
            org_name=a.org_name,
            job_title=a.job_title,
            search_method=a.search_method,
            apply_method=a.apply_method,
            contact_dept=a.contact_dept,
            result=a.result,
            planned=a.planned,
            hours=float(a.hours) if a.hours is not None else None,
            source=a.source,
            has_evidence=bool(evidence.get(a.activity_id)),
        )
        for a in activities
    ]


def current_round(rounds: list[Round], today: date) -> Round:
    found = next((r for r in rounds if r.period_start <= today <= r.recognition_date), None)
    if found is None:
        raise NotFoundError(code=ErrorCode.NO_ACTIVE_ROUND)
    return found


def round_of(rounds: list[Round], day: date) -> Round | None:
    """그 날짜가 대상기간에 들어가는 회차. 활동은 날짜만 저장하고 회차는 이렇게 계산합니다."""
    return next((r for r in rounds if r.period_start <= day <= r.recognition_date), None)


def _standard(rounds: list[Round], target: Round) -> bool:
    previous = next((r for r in rounds if r.round_no == target.round_no - 1), None)
    return previous is None or periods.is_standard_period(
        previous.recognition_date, target.recognition_date
    )


def evaluate(db: Session, user_id: uuid.UUID, today: date) -> RoundContext:
    """지금 회차를 계산합니다. 지금 회차가 없으면 404 NO_ACTIVE_ROUND."""
    rounds = repo.list_rounds(db, user_id)
    return evaluate_round(db, user_id, current_round(rounds, today), rounds, today)


def evaluate_round(
    db: Session, user_id: uuid.UUID, target: Round, rounds: list[Round], today: date
) -> RoundContext:
    """회차 하나를 계산합니다. 신청서(지난 회차 포함)도 이 결과로 활동 칸을 만듭니다."""
    procedure = repo.get_procedure(db, user_id)
    group = procedure.recipient_group if procedure else DEFAULT_GROUP
    activities = to_inputs(db, activity_repo.list_all(db, user_id))
    # 이번 회차는 대상기간 안 활동(예정 포함). 지난 회차는 누적 한도·W3에만 씁니다.
    current = [
        a for a in activities if target.period_start <= a.activity_date <= target.recognition_date
    ]
    history = [a for a in activities if a.activity_date < target.period_start]
    result = check_round(
        round_no=target.round_no,
        group=group,
        period_start=target.period_start,
        period_end=target.period_end,
        standard_period=_standard(rounds, target),
        activities=current,
        history=history,
        today=today,
    )
    return RoundContext(target, rounds, group, current, result)


def to_round_check(db: Session, user_id: uuid.UUID, context: RoundContext, today: date):
    summary = next(
        s
        for s in account_service.read_rounds(db, user_id, today)
        if s.round == context.target.round_no
    )
    result = context.result
    period_days = (context.target.period_end - context.target.period_start).days + 1
    return RoundCheck(
        **summary.model_dump(),
        d_day=(context.target.recognition_date - today).days,
        rule_group=context.group,
        period_days=period_days,
        required=result.required,
        required_job_search=result.required_job_search,
        counted=result.counted,
        counted_job_search=result.counted_job_search,
        remaining=result.remaining,
        remaining_job_search=result.remaining_job_search,
        check_status=result.check_status,
        weeks=result.weeks,
        activities=result.activities,
        warnings=result.warnings,
        limits_used=result.limits_used,
        rule_refs=result.rule_refs,
    )


def read_current(db: Session, user_id: uuid.UUID, today: date) -> RoundCheck:
    """`GET /rounds/current`: 지금 회차 점검 (F-18)."""
    return to_round_check(db, user_id, evaluate(db, user_id, today), today)


# 회차 점검 결과를 통째로 바꾸는 form_update 경로 (패널 B가 다시 그림)
ROUND_CHECK_PATH = "/round_check"


def activity_update(activity: Activity, op: str = "add") -> FormUpdate:
    """활동 한 건이 바뀐 것을 패널 B(form: activities)에 알립니다."""
    return FormUpdate(
        form=FormName.ACTIVITIES,
        path=f"/activities/{activity.activity_id}",
        op=op,
        value=None
        if op == "remove"
        else {
            "activity_id": str(activity.activity_id),
            "activity_date": activity.activity_date.isoformat(),
            "category": activity.category,
            "kind": activity.kind,
            "route": activity.route,
            "org_name": activity.org_name,
            "planned": activity.planned,
            "source": activity.source,
        },
    )


def round_check_update(db: Session, user_id: uuid.UUID, today: date) -> FormUpdate:
    """활동을 넣거나 뺀 뒤 다시 계산한 회차 점검 (F-17·F-20)."""
    return FormUpdate(
        form=FormName.ACTIVITIES,
        path=ROUND_CHECK_PATH,
        op="replace",
        value=read_current(db, user_id, today).model_dump(mode="json"),
    )
