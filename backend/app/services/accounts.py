"""시연 계정 입장·조회·삭제를 처리하는 핵심 서비스입니다.

입장하면 그 방문자의 계정이 있으면 그대로 쓰고, 없으면 seed를 오늘 날짜 기준으로 바꿔
기본정보, 절차 상태, 이력서, 회차와 회차별 신청서, 미리 넣은 활동까지 한 번에 만듭니다.
조회할 때는 오늘 날짜로 지금 회차를 다시 진단하고 첫 화면(진입 결과)을 정합니다.
삭제하면 그 계정의 데이터와 업로드 폴더를 지워, 다시 입장하면 처음 상태로 시작합니다.
"""

import shutil
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agent import checkpointer
from app.core import crypto
from app.core.clock import KST
from app.core.config import get_settings
from app.core.db import create_or_existing
from app.core.errors import ConflictError, NotFoundError
from app.repositories import accounts as repo
from app.repositories import imports as import_repo
from app.repositories import messages as message_repo
from app.rules import notices as notice_rules
from app.rules import periods, presubmit
from app.rules import resume as resume_rules
from app.rules.entry_text import WELCOME_NEW, WELCOME_RETURNING, RoundFacts
from app.schemas.accounts import AccountRead, PersonaCard, PersonaDisplay, PersonaList
from app.schemas.application import SubmitMode
from app.schemas.common import ErrorCode
from app.schemas.forms import recognition as recognition_form
from app.schemas.forms import resume as resume_form
from app.schemas.imports import ImportKind
from app.schemas.procedure import ProcedureRead, Stage
from app.schemas.resume import ResumeStatus
from app.schemas.rounds import ActivityStatus, ApplicationStatus, RoundStatus, RoundSummary
from app.services import messages as message_service
from app.services.entry import ResumeState, build_entry, situation_rule_refs
from app.services.seed import at

# seed에서 이미 낸 회차는 인정일 이 시각에 낸 것으로 둡니다.
SEED_SUBMITTED_AT = time(10)
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
    db: Session, visitor_id: uuid.UUID, persona_id: str, now: datetime
) -> tuple[AccountRead, bool]:
    """있으면 그대로, 없으면 seed로 만듭니다. 두 번째 값은 새로 만들었는지."""
    today = now.date()
    persona = _persona_or_404(db, persona_id)
    user = repo.get_user(db, visitor_id, persona_id)
    created = False
    if user is None:

        def create() -> repo.User:
            new = repo.new_user(visitor_id, persona_id, today)
            repo.add_all(db, [new])
            _materialize(db, new.user_id, persona.seed, today)
            return new

        # 같은 계정 입장이 동시에 오면 먼저 만들어진 계정을 이어서 돌려줍니다(PUT은 멱등).
        user, created = create_or_existing(
            db, create, lambda: repo.get_user(db, visitor_id, persona_id)
        )
    elif not import_repo.has_any(db, user.user_id):
        # 불러오기 테이블(0003)보다 먼저 만든 계정은 입장할 때 seed 목록을 채웁니다.
        # 동시 입장으로 같은 행이 먼저 들어갔으면 그대로 둡니다(생성 여부는 버림: 기존 계정).
        existing = user

        def backfill() -> repo.User:
            repo.add_all(db, _import_rows(existing.user_id, persona.seed, existing.anchor_date))
            return existing

        user, _ = create_or_existing(db, backfill, lambda: existing)
    account = AccountContext(user.user_id, user.persona_id, user.anchor_date)
    return read_account(db, account, now, greet=True), created


def delete_account(db: Session, account: AccountContext) -> None:
    """계정 행과 함께 대화 그래프 상태(체크포인트, thread_id=user_id)와 업로드 파일을 지웁니다.

    체크포인트를 먼저 지웁니다. 여기서 실패하면 계정 행이 그대로 남아 DELETE를 다시 보내면 됩니다.
    체크포인트는 별도 연결(autocommit)에서 지워지므로, 그 뒤 `db.commit()`이 실패하면 체크포인트만
    지워지고 계정 행·업로드 폴더는 남을 수 있습니다. 이때도 계정이 남아 있어 DELETE를 다시 보내면
    정리됩니다(없는 thread를 지워도 오류가 나지 않습니다).
    """
    # 답을 만드는 턴이 이 계정을 잠그고 있으면 기다리지 않고 바로 알립니다(초기화가 멈추지 않게).
    if not message_repo.try_lock_turn(db, account.user_id):
        raise ConflictError(code=ErrorCode.TURN_IN_PROGRESS)
    checkpointer.get_checkpointer().delete_thread(str(account.user_id))
    user = repo.get_user_by_id(db, account.user_id)
    if user is not None:
        repo.delete_user(db, user)
        db.commit()
    shutil.rmtree(Path(get_settings().upload_dir) / str(account.user_id), ignore_errors=True)


def read_account(
    db: Session, account: AccountContext, now: datetime, *, greet: bool = False
) -> AccountRead:
    """계정 상태. 지금 시각(KST)으로 인정일 마감(17·18시)과 알림까지 서버가 판정합니다.

    `greet`: 입장·새로고침이면 첫 안내 앞에 인사를 붙입니다(처음이면 도우미 소개, 대화 기록이
    있으면 "다시 오셨네요"). 저장 같은 동작 뒤에 다시 만드는 안내는 인사 없이 지금 상황만 줍니다.
    """
    today = now.date()
    procedure = read_procedure(db, account.user_id, today)
    rounds = read_rounds(db, account.user_id, today)
    current = next((r for r in rounds if r.status == RoundStatus.CURRENT), None)
    deadline = notice_rules.round_deadline(current, now) if current else None
    d_day = deadline.d_day if deadline else None
    resume_state = _resume_status(db, account.user_id, procedure)
    entry = build_entry(
        procedure,
        resume_state,
        current,
        d_day,
        name=_display_name(db, account.persona_id),
        old_resume_year=_old_resume_year(db, account.user_id, resume_state),
        round_facts=_round_facts(db, account.user_id, today) if current else None,
        welcome=_welcome(db, account.user_id) if greet else None,
        resume_filled=_resume_filled(db, account.user_id, resume_state),
    )
    return AccountRead(
        persona_id=account.persona_id,
        today=today,
        procedure=procedure,
        current_round=current,
        deadline=deadline,
        notices=notice_rules.account_notices(
            procedure, current, deadline, notice_rules.missed_round(rounds, today)
        ),
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
        online_presubmit=presubmit.online_presubmit(state.age_at_separation),
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


def _display_name(db: Session, persona_id: str) -> str:
    """첫 안내의 {이름}: 가상 계정 카드의 표시 이름 (개인정보 칸 user_profiles가 아님, 1.2)."""
    persona = repo.get_persona(db, persona_id)
    return str((persona.display or {}).get("name", "")) if persona else ""


def _old_resume_year(db: Session, user_id: uuid.UUID, state: ResumeState | None) -> int | None:
    """E7b 첫 안내의 '{연도}년에 쓰신 이력서'."""
    if state != ResumeState.OUTDATED:
        return None
    resume = repo.get_resume(db, user_id)
    return resume.saved_at.astimezone(KST).year if resume and resume.saved_at else None


def _round_facts(db: Session, user_id: uuid.UUID, today: date) -> RoundFacts | None:
    """E4b 현황 요약(T-S)에 쓸 이번 회차 점검 값.

    회차 점검 서비스가 이 모듈을 쓰므로 함수 안에서 불러옵니다.
    """
    from app.services import rounds as round_service  # noqa: PLC0415 - 순환 import 피하기

    result = round_service.evaluate(db, user_id, today).result
    recorded = sum(
        1
        for a in result.activities
        if a.status not in (ActivityStatus.PLANNED, ActivityStatus.OUT_OF_PERIOD)
    )
    return RoundFacts(
        required=result.required,
        required_job_search=result.required_job_search,
        recorded=recorded,
        counted=result.counted,
        counted_job_search=result.counted_job_search,
        weekly=bool(result.weeks),
        same_day=sum(1 for a in result.activities if a.status == ActivityStatus.SAME_DAY),
    )


def situation_rules(
    db: Session,
    user_id: uuid.UUID,
    procedure: ProcedureRead,
    round_: RoundSummary | None,
    d_day: int | None,
) -> list[str]:
    """지금 단계·회차의 근거 규칙 카드(첫 안내와 같은 분기). 대화에서 근거로 미리 붙입니다."""
    return situation_rule_refs(procedure, _resume_status(db, user_id, procedure), round_, d_day)


def resume_ready(db: Session, user_id: uuid.UUID, procedure: ProcedureRead) -> bool:
    """이직 뒤에 저장한 이력서가 있는지. 화면 안내(entry)와 다음 할 일이 같은 기준을 씁니다."""
    return _resume_status(db, user_id, procedure) == ResumeState.READY


def _welcome(db: Session, user_id: uuid.UUID) -> str:
    return WELCOME_RETURNING if message_service.has_history(db, user_id) else WELCOME_NEW


def _resume_filled(db: Session, user_id: uuid.UUID, state: ResumeState | None) -> int | None:
    """쓰는 중이거나 예전 이력서면 꼭 채울 5칸 중 몇 칸을 채웠는지."""
    if state not in (ResumeState.DRAFT, ResumeState.OUTDATED):
        return None
    # 이력서 서비스가 이 모듈을 쓰므로 여기서 가져옵니다(순환 import 피하기).
    from app.services.resume import read_resume_data  # noqa: PLC0415

    data = read_resume_data(repo.get_resume(db, user_id))
    return resume_rules.resume_completeness(data).filled


def _resume_status(db: Session, user_id: uuid.UUID, procedure: ProcedureRead) -> ResumeState | None:
    """1장 1.2 resume_status: 없음(None) / outdated / draft / ready."""
    resume = repo.get_resume(db, user_id)
    if resume is None:
        return None
    if resume.status == ResumeStatus.DRAFT:
        return ResumeState.DRAFT
    saved_on = resume.saved_at.astimezone(KST).date() if resume.saved_at else None
    if saved_on is None or resume_rules.saved_before_separation(
        saved_on, procedure.separation_date
    ):
        return ResumeState.OUTDATED
    return ResumeState.READY


# ── seed → 계정 행 ─────────────────────────────────────────────


def _import_rows(user_id: uuid.UUID, seed: dict[str, Any], anchor: date) -> list[repo.Work24Import]:
    """seed의 고용24 불러오기 목록 → work24_imports 행."""
    rows: list[repo.Work24Import] = []
    imports = seed.get("imports") or {}
    for kind, key in (
        (ImportKind.CAREER_CERTIFICATE, "career_certificates"),
        (ImportKind.JOB_APPLICATION, "job_applications"),
    ):
        for position, raw in enumerate(imports.get(key, [])):
            rows.append(
                repo.Work24Import(
                    user_id=user_id,
                    source_id=raw["import_id"],
                    kind=kind,
                    category=raw["category"],
                    title=raw["title"],
                    detail=raw["detail"],
                    item_date=at(anchor, raw.get("date_offset")),
                    position=position,
                    is_recorded=bool(raw.get("is_recorded", False)),
                )
            )
    return rows


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
                data=seed_resume(resume["data"], resume["field_status"]).model_dump(mode="json"),
                saved_at=datetime.combine(saved_on, datetime.min.time(), KST) if saved_on else None,
            )
        )
    rows.extend(_import_rows(user_id, seed, anchor))
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


def create_rounds(db: Session, user_id: uuid.UUID, state: repo.ProcedureState) -> None:
    """1차 인정일이 들어오면 종료 예정일까지 회차와 회차별 신청서(draft)를 만듭니다 (F-28)."""
    assert state.eligibility_applied_on and state.first_recognition_date
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
                status=ApplicationStatus.SUBMITTED if submitted else ApplicationStatus.DRAFT,
                submit_mode=_submit_mode(p) if submitted else None,
                submitted_at=(
                    datetime.combine(p.recognition_date, SEED_SUBMITTED_AT, KST)
                    if submitted
                    else None
                ),
                data=data.model_dump(mode="json"),
            )
        )
    repo.add_all(db, applications)


def _submit_mode(planned: periods.PlannedRound) -> SubmitMode:
    """seed에서 이미 낸 회차의 제출 방식: 출석 회차면 출석, 아니면 온라인 제출."""
    return SubmitMode.ATTEND if planned.attendance_required else SubmitMode.SEND


# 칸이 아니라 칸을 담는 묶음. 나머지 dict 값(희망임금 등)은 칸 하나의 값입니다.
_RESUME_GROUPS = {"job_preferences", "competencies", "additional_info"}


def seed_resume(data: dict[str, Any], status: str) -> resume_form.ResumeData:
    """seed의 값만 있는 이력서를 칸마다 {value, status, source=seed}로 감쌉니다."""

    def field(value: Any) -> dict[str, Any]:
        return {"value": value, "status": status, "source": "seed"}

    def item(raw: dict[str, Any]) -> dict[str, Any]:
        return {k: v if k == "item_id" else field(v) for k, v in raw.items()}

    def wrap(raw: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in raw.items():
            if key in _RESUME_GROUPS:
                out[key] = wrap(value)
            elif isinstance(value, list) and all(
                isinstance(v, dict) and "item_id" in v for v in value
            ):
                out[key] = [item(v) for v in value]
            else:
                out[key] = field(value)
        return out

    return resume_form.ResumeData.model_validate(wrap(data))


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
