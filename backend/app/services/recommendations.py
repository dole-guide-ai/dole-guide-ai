"""부족한 활동 추천과 추천을 예정 활동으로 넣기 (F-19, 상세기획 2-2.8).

부족 건수는 이번 회차 신청서와 같은 계산(같은 날 1건, 예정 활동 제외)으로 셉니다. 회차 점검(F-18)의
`check_round`가 붙으면 그 결과를 쓰도록 바꿉니다.
"""

import uuid
from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, NotImplementedYetError
from app.models import Activity
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.rules import application as form_rules
from app.rules import recommend as rules
from app.schemas.activities import ActivityCreate
from app.schemas.common import ErrorCode, FieldSource, FormName, FormUpdate, UpdatesRead
from app.schemas.rounds import Recommendation, RecommendationList
from app.services import idempotency
from app.services.accounts import AccountContext
from app.services.application import CURRENT, activity_inputs, find_round

NOT_RECOMMENDED_MESSAGE = "지금 추천 목록에 없는 활동이에요. 추천을 다시 불러와 주세요."
DUPLICATE_MESSAGE = "이미 예정으로 넣은 활동이에요."
PLANNED_NOT_FOUND_MESSAGE = "예정 활동을 찾지 못했어요."
NOT_PLANNED_MESSAGE = "이미 한 활동으로 기록돼 있어요."
DONE_DATE_MESSAGE = "한 날은 이번 회차 대상기간 안이고 오늘까지여야 해요."


def _desired_occupation(db: Session, user_id: uuid.UUID) -> str | None:
    resume = repo.get_resume(db, user_id)
    occupations = ((resume.data if resume else {}).get("job_preferences") or {}).get(
        "desired_occupations"
    ) or []
    return next((o.get("name") for o in occupations if o.get("name")), None)


def _current(db: Session, account: AccountContext, today: date):
    target, _ = find_round(db, account.user_id, CURRENT, today)
    procedure = repo.get_procedure(db, account.user_id)
    group = procedure.recipient_group if procedure else "general"
    inputs = activity_inputs(db, account.user_id, target.period_start, target.period_end)
    form = form_rules.build_form_activities(inputs, target.period_start, target.period_end)
    required, required_job = form_rules.required_activities(group, target.round_no)
    counted, counted_job = len(form.job_search) + len(form.other), len(form.job_search)
    picks = rules.recommend_activities(
        shortfall=max(required - counted, 0),
        shortfall_job_search=max(required_job - counted_job, 0),
        group=group,
        round_no=target.round_no,
        lectures_used=activity_repo.count_done_kind(db, account.user_id, "lecture"),
        desired_occupation=_desired_occupation(db, account.user_id),
    )
    busy = [a.activity_date for a in inputs if not a.planned]
    return target, picks, inputs, busy


def list_recommendations(db: Session, account: AccountContext, today: date) -> RecommendationList:
    target, picks, _, busy = _current(db, account, today)
    items = [
        Recommendation(
            recommendation_id=rules.recommendation_id(target.round_no, pick.candidate.key),
            category=pick.candidate.category,
            kind=pick.candidate.kind,
            title=pick.title,
            reason=pick.reason,
            evidence_hint=pick.candidate.evidence,
            external={"rule_refs": list(pick.candidate.rule_refs)},
        )
        for pick in picks
    ]
    return RecommendationList(
        items=items,
        total=len(items),
        deadline_text=rules.deadline_text(target.recognition_date, busy),
    )


def _activity_update(activity: Activity, op: str = "add") -> FormUpdate:
    return FormUpdate(
        form=FormName.ACTIVITIES,
        path=f"/activities/{activity.activity_id}",
        op=op,
        value={
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


def add_recommended(
    db: Session, account: AccountContext, recommendation_id: str, today: date
) -> UpdatesRead:
    """추천 `선택`: 그 활동을 예정(planned)으로 이번 회차에 넣습니다. 계산에는 넣지 않습니다."""
    target, picks, inputs, _ = _current(db, account, today)
    parsed = rules.parse_recommendation_id(recommendation_id)
    if parsed is None or parsed[0] != target.round_no:
        raise ConflictError(code=ErrorCode.CONFLICT, message=NOT_RECOMMENDED_MESSAGE)
    candidate = parsed[1]
    if candidate.key not in {pick.candidate.key for pick in picks}:
        raise ConflictError(code=ErrorCode.CONFLICT, message=NOT_RECOMMENDED_MESSAGE)
    if any(a.planned and a.kind == candidate.kind and a.route == candidate.route for a in inputs):
        raise ConflictError(code=ErrorCode.DUPLICATE_ACTIVITY, message=DUPLICATE_MESSAGE)

    # 예정일은 권장 기한(인정일 전날)으로 두고, 했다고 하면 실제 날짜로 바꿉니다.
    planned_on = max(rules.planned_date(target.recognition_date), today)
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
    return UpdatesRead(updates=[_activity_update(activity)])


def create_activity(
    db: Session,
    account: AccountContext,
    body: ActivityCreate,
    idempotency_key: str | None,
    today: date,
) -> UpdatesRead:
    """활동 추가. 추천 넣기(`recommendation_id`)만 여기서 합니다.

    직접 기록은 활동 기록(F-17)이 붙입니다.
    """
    if body.recommendation_id is None:
        raise NotImplementedYetError()
    recommendation = body.recommendation_id
    return idempotency.run_once(
        db,
        account.user_id,
        idempotency_key,
        body.model_dump(mode="json"),
        UpdatesRead,
        lambda: add_recommended(db, account, recommendation, today),
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
    return UpdatesRead(updates=[_activity_update(activity, "replace")])
