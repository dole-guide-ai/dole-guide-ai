"""시연 계정 입장·조회·삭제를 처리하는 핵심 서비스입니다.

입장하면 그 방문자의 계정이 있으면 그대로 쓰고, 없으면 seed를 오늘 날짜 기준으로 바꿔
기본정보, 절차 상태, 이력서, 회차와 회차별 신청서, 미리 넣은 활동까지 한 번에 만듭니다.
조회할 때는 오늘 날짜로 지금 회차를 다시 진단하고 첫 화면(진입 결과)을 정합니다.
삭제하면 그 계정의 데이터와 업로드 폴더를 지워, 다시 입장하면 처음 상태로 시작합니다.
"""

import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import crypto
from app.core.clock import KST
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.repositories import accounts as repo
from app.rules import periods
from app.schemas.accounts import AccountRead, PersonaCard, PersonaDisplay, PersonaList
from app.schemas.common import ErrorCode
from app.schemas.forms import recognition as recognition_form
from app.schemas.forms import resume as resume_form
from app.schemas.procedure import ProcedureRead, Stage
from app.schemas.rounds import ApplicationStatus, RoundStatus, RoundSummary
from app.services import messages as message_service
from app.services.entry import build_entry
from app.services.seed import at

ENDED_MESSAGE = "실업급여 수급이 끝나서 더 고칠 수 없어요."

STAGE_LABEL = {
    "job_registration": "구직등록 중",
    "education": "온라인 교육 중",
    "eligibility_application": "수급자격 신청 준비",
    "eligibility_applied": "1차 인정일 대기",
    "recognition": "실업인정 중",
    "ended": "수급 종료",
}


@dataclass(frozen=True)
class AccountContext:
    """라우터가 의존성으로 받는 현재 계정. 모든 계정 데이터 쿼리는 user_id로 거릅니다."""

    user_id: uuid.UUID
    persona_id: str
    anchor_date: date


def _persona_or_404(db: Session, persona_id: str):
    persona = repo.get_persona(db, persona_id)
    if persona is None:
        raise NotFoundError(code=ErrorCode.PERSONA_NOT_FOUND)
    return persona


def find_account(db: Session, visitor_id: uuid.UUID, persona_id: str) -> AccountContext:
    _persona_or_404(db, persona_id)
    user = repo.get_user(db, visitor_id, persona_id)
    if user is None:
        raise NotFoundError(code=ErrorCode.ACCOUNT_NOT_FOUND)
    return AccountContext(user.user_id, user.persona_id, user.anchor_date)


def list_persona_cards(db: Session, visitor_id: uuid.UUID) -> PersonaList:
    entered = {}
    for user in repo.list_users(db, visitor_id):
        procedure = repo.get_procedure(db, user.user_id)
        if procedure is not None:
            entered[user.persona_id] = STAGE_LABEL.get(procedure.stage)
    cards = [
        PersonaCard(
            persona_id=p.persona_id,
            display=PersonaDisplay(**p.display),
            progress_summary=entered.get(p.persona_id),
        )
        for p in repo.list_personas(db)
    ]
    return PersonaList(items=cards, total=len(cards))


def enter(
    db: Session, visitor_id: uuid.UUID, persona_id: str, today: date
) -> tuple[AccountRead, bool]:
    """있으면 그대로, 없으면 seed로 만듭니다. 두 번째 값은 새로 만들었는지."""
    persona = _persona_or_404(db, persona_id)
    user = repo.get_user(db, visitor_id, persona_id)
    created = user is None
    if user is None:
        try:
            user = repo.new_user(visitor_id, persona_id, today)
            repo.add_all(db, [user])
            _materialize(db, user.user_id, persona.seed, today)
            db.commit()
        except IntegrityError:
            # 버튼 두 번·탭 두 개처럼 같은 계정 입장이 동시에 오면 한쪽만 만들어집니다.
            # 늦은 쪽은 되돌리고 먼저 만들어진 계정을 이어서 돌려줍니다.
            # PUT은 여러 번 보내도 결과가 같아야 하기 때문입니다.
            db.rollback()
            user = repo.get_user(db, visitor_id, persona_id)
            if user is None:
                raise
            created = False
    account = AccountContext(user.user_id, user.persona_id, user.anchor_date)
    return read_account(db, account, today), created


def delete_account(db: Session, account: AccountContext) -> None:
    user = repo.get_user_by_id(db, account.user_id)
    if user is not None:
        repo.delete_user(db, user)
        db.commit()
    shutil.rmtree(Path(get_settings().upload_dir) / str(account.user_id), ignore_errors=True)


def read_account(db: Session, account: AccountContext, today: date) -> AccountRead:
    procedure = read_procedure(db, account.user_id, today)
    rounds = read_rounds(db, account.user_id, today)
    current = next((r for r in rounds if r.status == RoundStatus.CURRENT), None)
    if current is None:
        # 대기기간(신청일부터 7일) 중에는 1회차가 아직 시작 전이라 다가올 회차를 보여 줍니다.
        current = next((r for r in rounds if r.status == RoundStatus.UPCOMING), None)
    d_day = (current.recognition_date - today).days if current else None
    entry = build_entry(procedure, _resume_status(db, account.user_id, procedure), current, d_day)
    return AccountRead(
        persona_id=account.persona_id,
        today=today,
        procedure=procedure,
        current_round=current,
        entry=entry,
        # 새로고침하면 답을 기다리던 질문과 선택지를 다시 띄웁니다 (F-03).
        pending_ask=message_service.pending_ask(db, account.user_id),
    )


def _end_dates(state) -> tuple[date | None, date]:
    benefit_end = (
        periods.benefit_end_date(state.eligibility_applied_on, state.benefit_days)
        if state.eligibility_applied_on
        else None
    )
    return benefit_end, periods.period_end_date(state.separation_date)


def _close_if_ended(db: Session, user_id: uuid.UUID, today: date) -> None:
    """실업인정 중인데 종료 예정일이 지났으면 단계를 ended로 바꿉니다 (서버 진단, F-33).

    마지막 회차의 인정일은 종료 예정일보다 뒤일 수 있어서, 그 인정일까지 지나야 끝냅니다.
    """
    state = repo.get_procedure(db, user_id)
    if state is None or state.stage != Stage.RECOGNITION:
        return
    reason = periods.end_reason_on(today, *_end_dates(state))
    recognition_dates = [r.recognition_date for r in repo.list_rounds(db, user_id)]
    if reason is None or periods.remaining_rounds(recognition_dates, today) > 0:
        return
    state.stage = Stage.ENDED
    state.end_reason = reason
    db.commit()


def ensure_not_ended(db: Session, user_id: uuid.UUID) -> None:
    """수급이 끝난 계정은 활동·신청서·절차를 고칠 수 없습니다 (F-33).

    쓰기 서비스 앞에서 부릅니다.
    """
    state = repo.get_procedure(db, user_id)
    if state is not None and state.stage == Stage.ENDED:
        raise ConflictError(code=ErrorCode.STAGE_ORDER, message=ENDED_MESSAGE)


def read_procedure(db: Session, user_id: uuid.UUID, today: date | None = None) -> ProcedureRead:
    """절차 상태를 돌려줍니다.

    오늘 날짜를 주면 먼저 종료 진단을 해서 계정 조회와 절차 조회가 같은 단계를 돌려줍니다.
    """
    if today is not None:
        _close_if_ended(db, user_id, today)
    state = repo.get_procedure(db, user_id)
    if state is None:
        raise NotFoundError(code=ErrorCode.ACCOUNT_NOT_FOUND)
    benefit_end, period_end = _end_dates(state)
    recognition_dates = [r.recognition_date for r in repo.list_rounds(db, user_id)]
    return ProcedureRead(
        stage=state.stage,
        recipient_group=state.recipient_group,
        age_at_separation=state.age_at_separation,
        has_disability=state.has_disability,
        separation_date=state.separation_date,
        education_done=state.education_done,
        eligibility_applied_on=state.eligibility_applied_on,
        first_recognition_date=state.first_recognition_date,
        benefit_days=state.benefit_days,
        benefit_end_date=benefit_end,
        period_end_date=period_end,
        expected_end_date=periods.expected_end_date(benefit_end, period_end),
        end_reason=state.end_reason,
        remaining_rounds=(
            periods.remaining_rounds(recognition_dates, today)
            if recognition_dates and today
            else None
        ),
        last_round=len(recognition_dates) or None,
    )


def read_rounds(db: Session, user_id: uuid.UUID, today: date) -> list[RoundSummary]:
    summaries = []
    for r in repo.list_rounds(db, user_id):
        if today > r.recognition_date:
            status = RoundStatus.CLOSED
        elif today >= r.period_start:
            status = RoundStatus.CURRENT
        else:
            status = RoundStatus.UPCOMING
        application = repo.get_application(db, r.round_id)
        summaries.append(
            RoundSummary(
                round=r.round_no,
                period_start=r.period_start,
                period_end=r.period_end,
                recognition_date=r.recognition_date,
                attendance_required=r.attendance_required,
                status=status,
                application_status=application.status if application else ApplicationStatus.DRAFT,
            )
        )
    return summaries


def resume_is_saved(db: Session, user_id: uuid.UUID) -> bool:
    """구직등록용 이력서를 이직 뒤에 저장했는지(resume_status = ready).

    교육 이수를 표시하기 전에 봅니다 (F-16).
    """
    return _resume_status(db, user_id, read_procedure(db, user_id)) == "ready"


def create_rounds(db: Session, user_id: uuid.UUID, state: Any) -> None:
    """1차 인정일이 들어온 계정에 회차와 회차별 빈 신청서를 만듭니다 (F-16, 설계 3.4)."""
    _materialize_rounds(
        db,
        user_id,
        {},
        state.recipient_group,
        state.eligibility_applied_on,
        state.first_recognition_date,
        state.benefit_days,
        state.separation_date,
    )


def _resume_status(db: Session, user_id: uuid.UUID, procedure: ProcedureRead) -> str | None:
    """1장 1.2 resume_status: none / outdated / draft / ready."""
    resume = repo.get_resume(db, user_id)
    if resume is None:
        return None
    if resume.status == "draft":
        return "draft"
    saved_on = resume.saved_at.astimezone(KST).date() if resume.saved_at else None
    if saved_on is None or saved_on <= procedure.separation_date:
        return "outdated"
    return "ready"


# ── seed → 계정 행 ─────────────────────────────────────────────


def _materialize(db: Session, user_id: uuid.UUID, seed: dict[str, Any], anchor: date) -> None:
    proc = seed["procedure"]
    profile = seed["profile"]
    account_number = profile.get("account_number")
    rows: list[object] = [
        repo.UserProfile(
            user_id=user_id,
            name=profile["name"],
            birth_year=profile.get("birth_year"),
            gender=profile.get("gender"),
            phone=profile.get("phone"),
            email=profile.get("email"),
            address=profile.get("address"),
            bank_name=profile.get("bank_name"),
            account_number_enc=crypto.encrypt(account_number) if account_number else None,
            account_last4=crypto.last4(account_number) if account_number else None,
        )
    ]
    separation = at(anchor, proc["separation_offset"])
    applied = at(anchor, proc["eligibility_applied_offset"])
    first_recognition = at(anchor, proc["first_recognition_offset"])
    insured = float(proc["insured_years"])
    days = periods.benefit_days(proc["age_at_separation"], proc["has_disability"], insured)
    rows.append(
        repo.ProcedureState(
            user_id=user_id,
            stage=proc["stage"],
            recipient_group=proc["recipient_group"],
            separation_date=separation,
            age_at_separation=proc["age_at_separation"],
            has_disability=proc["has_disability"],
            insured_years=Decimal(str(insured)),
            benefit_days=days,
            education_done=proc["education_done"],
            eligibility_applied_on=applied,
            first_recognition_date=first_recognition,
        )
    )
    if resume := seed.get("resume"):
        saved_on = at(anchor, resume.get("saved_offset"))
        rows.append(
            repo.Resume(
                user_id=user_id,
                schema_version=resume_form.SCHEMA_VERSION,
                status=resume["status"],
                data=resume_form.ResumeData.model_validate(resume["data"]).model_dump(mode="json"),
                saved_at=datetime.combine(saved_on, datetime.min.time(), KST) if saved_on else None,
            )
        )
    for activity in seed.get("activities", []):
        rows.append(
            repo.Activity(
                user_id=user_id,
                activity_date=at(anchor, activity["date_offset"]),
                category=activity["category"],
                kind=activity["kind"],
                route=activity.get("route"),
                org_name=activity.get("org_name"),
                source=activity["source"],
            )
        )
    repo.add_all(db, rows)
    if applied and first_recognition:
        _materialize_rounds(
            db, user_id, seed, proc["recipient_group"], applied, first_recognition, days, separation
        )


def _materialize_rounds(
    db: Session,
    user_id: uuid.UUID,
    seed: dict[str, Any],
    group: str,
    applied: date,
    first_recognition: date,
    days: int,
    separation: date,
) -> None:
    end = periods.expected_end_date(
        periods.benefit_end_date(applied, days), periods.period_end_date(separation)
    )
    planned = periods.build_rounds(group, applied, first_recognition, end)
    rounds = [
        repo.Round(
            user_id=user_id,
            round_no=p.round_no,
            period_start=p.period_start,
            period_end=p.period_end,
            recognition_date=p.recognition_date,
            attendance_required=p.attendance_required,
        )
        for p in planned
    ]
    repo.add_all(db, rounds)
    submitted_through = seed.get("submitted_through_round", 0)
    prev = _prev_answers(seed.get("prev_answers"), planned, submitted_through)
    applications = []
    for r, p in zip(rounds, planned, strict=True):
        submitted = p.round_no <= submitted_through
        data = (
            prev
            if submitted and p.round_no == submitted_through
            else recognition_form.RecognitionData()
        )
        applications.append(
            repo.RecognitionApplication(
                round_id=r.round_id,
                user_id=user_id,
                status="submitted" if submitted else "draft",
                submit_mode=("attend" if p.attendance_required else "send") if submitted else None,
                submitted_at=(
                    datetime.combine(p.recognition_date, datetime.min.time(), KST)
                    + timedelta(hours=10)
                    if submitted
                    else None
                ),
                data=data.model_dump(mode="json"),
            )
        )
    repo.add_all(db, applications)


def _prev_answers(
    answers: dict[str, Any] | None,
    planned: list[periods.PlannedRound],
    submitted_through: int,
) -> recognition_form.RecognitionData:
    """직전 회차에 사용자가 답한 값을 seed에서 신청서 칸으로 옮깁니다 (source = user_answer)."""
    data = recognition_form.RecognitionData()
    if not answers:
        return data

    def answered(value: Any, on: date | None) -> dict[str, Any]:
        return {"value": value, "status": "confirmed", "source": "user_answer", "answered_on": on}

    # 답한 날은 마지막으로 제출한 회차의 인정일입니다.
    last = next((p for p in planned if p.round_no == submitted_through), None)
    on = last.recognition_date if last else None
    payload = data.model_dump(mode="json")
    for key, value in (answers.get("credit") or {}).items():
        payload["credit"][key] = answered(value, on)
    if method := answers.get("notification_method"):
        payload["notification_method"] = answered(method, on)
    return recognition_form.RecognitionData.model_validate(payload)
