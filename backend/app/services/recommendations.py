"""부족한 활동 추천과 추천을 예정 활동으로 넣기 (F-19, 상세기획 2-2.8).

부족 건수와 누적 한도 사용 횟수는 회차 점검(F-18) `check_round` 결과를 그대로 씁니다.
"""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, ExternalUnavailableError, NotFoundError
from app.models import Activity
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.rules import recommend as rules
from app.schemas.common import ErrorCode, FieldSource, UpdatesRead
from app.schemas.rounds import Recommendation, RecommendationList
from app.services import accounts as account_service
from app.services import rounds as round_service
from app.services import trainings as training_service
from app.services.accounts import AccountContext
from app.services.application import CURRENT, find_round

LECTURE_KIND = "lecture"
NOT_RECOMMENDED_MESSAGE = "지금 추천 목록에 없는 활동이에요. 추천을 다시 불러와 주세요."
DUPLICATE_MESSAGE = "이미 예정으로 넣은 활동이에요."
PLANNED_NOT_FOUND_MESSAGE = "예정 활동을 찾지 못했어요."
NOT_PLANNED_MESSAGE = "이미 한 활동으로 기록돼 있어요."
DONE_DATE_MESSAGE = "한 날은 이번 회차 대상기간 안이고 오늘까지여야 해요."


def _current(db: Session, account: AccountContext, today: date):
    context = round_service.evaluate(db, account.user_id, today)
    target, result, inputs = context.target, context.result, context.inputs
    weekly = rules.is_weekly_job_search(context.group, target.round_no)
    picks = rules.recommend_activities(
        shortfall=result.remaining,
        shortfall_job_search=result.remaining_job_search,
        group=context.group,
        round_no=target.round_no,
        limits_used=result.limits_used,
        desired_occupation=training_service.desired_occupation(db, account.user_id),
        planned=frozenset((a.kind, a.route or "") for a in inputs if a.planned),
    )
    busy = [a.activity_date for a in inputs if not a.planned]
    return target, picks, inputs, busy, weekly


# 추천 카드에 붙이는 실제 일정 수 (설계 3.9: 카드 안에 붙임)
EXTERNAL_ITEMS = 2


def _external(
    candidate: rules.Candidate, occupation: str | None, today: date, now: datetime
) -> dict[str, Any]:
    """직업훈련은 훈련과정, 특강은 고용센터 특강·집단상담 일정을 붙입니다 (F-30).

    외부 조회가 안 되면 일정 없이 추천만 보여 줍니다(추천은 막지 않음).
    """
    external: dict[str, Any] = {"rule_refs": list(candidate.rule_refs)}
    try:
        if candidate.is_training:
            found = training_service.search_trainings(occupation, None, today, now)
            external["trainings"] = [t.model_dump() for t in found.items[:EXTERNAL_ITEMS]]
            external["source"] = found.source
        elif candidate.kind == LECTURE_KIND:
            programs = training_service.search_programs(None, now)
            external["programs"] = [p.model_dump() for p in programs.items[:EXTERNAL_ITEMS]]
            external["source"] = programs.source
    except ExternalUnavailableError:
        pass
    return external


def list_recommendations(db: Session, account: AccountContext, now: datetime) -> RecommendationList:
    today = now.date()
    target, picks, _, busy, weekly = _current(db, account, today)
    occupation = training_service.desired_occupation(db, account.user_id)
    items = [
        Recommendation(
            recommendation_id=rules.recommendation_id(target.round_no, pick.candidate.key),
            category=pick.candidate.category,
            kind=pick.candidate.kind,
            title=pick.title,
            reason=pick.reason,
            evidence_hint=pick.candidate.evidence,
            external=_external(pick.candidate, occupation, today, now),
        )
        for pick in picks
    ]
    return RecommendationList(
        items=items,
        total=len(items),
        deadline_text=rules.deadline_text(target.recognition_date, busy, weekly),
    )


def add_recommended(
    db: Session, account: AccountContext, recommendation_id: str, today: date
) -> UpdatesRead:
    """추천 `선택`: 그 활동을 예정(planned)으로 이번 회차에 넣습니다. 계산에는 넣지 않습니다."""
    # 다른 키로 같은 추천이 동시에 와도 중복 검사와 저장이 겹치지 않게 계정 단위로 줄 세웁니다.
    repo.lock_user(db, account.user_id)
    # 수급이 끝난 계정은 활동을 고칠 수 없습니다 (F-33 완료 기준).
    account_service.ensure_not_ended(db, account.user_id)
    target, picks, inputs, _, _ = _current(db, account, today)
    parsed = rules.parse_recommendation_id(recommendation_id)
    if parsed is None or parsed[0] != target.round_no:
        raise ConflictError(code=ErrorCode.CONFLICT, message=NOT_RECOMMENDED_MESSAGE)
    candidate = parsed[1]
    # 이미 넣은 추천은 목록에서 빠지므로, 목록 검사보다 먼저 중복으로 알려 줍니다.
    if any(a.planned and a.kind == candidate.kind and a.route == candidate.route for a in inputs):
        raise ConflictError(code=ErrorCode.DUPLICATE_ACTIVITY, message=DUPLICATE_MESSAGE)
    if candidate.key not in {pick.candidate.key for pick in picks}:
        raise ConflictError(code=ErrorCode.CONFLICT, message=NOT_RECOMMENDED_MESSAGE)

    # 예정일은 권장 기한(인정일 전날)으로 두고, 했다고 하면 실제 날짜로 바꿉니다.
    planned_on = rules.planned_date(target.recognition_date, today)
    activity = activity_repo.add(
        db,
        Activity(
            user_id=account.user_id,
            activity_date=planned_on,
            category=candidate.category,
            kind=candidate.kind,
            route=candidate.route,
            source=FieldSource.AUTO,
            planned=True,
        ),
    )
    return UpdatesRead(
        updates=[
            round_service.activity_update(activity),
            round_service.round_check_update(db, account.user_id, today),
        ]
    )


def mark_done(
    db: Session,
    account: AccountContext,
    activity_id: uuid.UUID,
    done_on: date,
    today: date,
    org_name: str | None = None,
) -> UpdatesRead:
    """사용자가 예정 활동을 "했어요"라고 하면 실제 활동으로 바꿉니다 (대화 도구가 부릅니다)."""
    account_service.ensure_not_ended(db, account.user_id)
    activity = activity_repo.get(db, account.user_id, activity_id)
    if activity is None:
        raise NotFoundError(message=PLANNED_NOT_FOUND_MESSAGE)
    if not activity.planned:
        raise ConflictError(code=ErrorCode.DUPLICATE_ACTIVITY, message=NOT_PLANNED_MESSAGE)
    target, _ = find_round(db, account.user_id, CURRENT, today)
    if not target.period_start <= done_on <= min(today, target.recognition_date):
        raise ConflictError(code=ErrorCode.ROUND_CLOSED, message=DONE_DATE_MESSAGE)
    activity.planned = False
    activity.activity_date = done_on
    activity.source = FieldSource.USER_ANSWER
    if org_name:
        activity.org_name = org_name
    db.commit()
    return UpdatesRead(
        updates=[
            round_service.activity_update(activity, "replace"),
            round_service.round_check_update(db, account.user_id, today),
        ]
    )
