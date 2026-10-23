"""회차별 실업인정 신청서를 조회하는 서비스입니다 (F-23).

신청서 행에는 본인 답변 칸만 저장하고, 구직활동 줄은 그 회차 대상기간의 인정 활동에서 매번 만듭니다.
지난 회차에 답한 통지 방법·실업크레딧은 이번 회차가 비어 있으면 불러와 보여 줍니다.
제출 방식·체크리스트는 지금 시각(KST)으로 계산하고(F-26),
제출과 본인 답변 저장(F-27)도 여기서 합니다.
"""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.etag import check_if_match
from app.core.json_patch import apply_patch
from app.repositories import accounts as repo
from app.rules import application as rules
from app.schemas.application import (
    ApplicationRead,
    Checklist,
    ChecklistItem,
    ExcludedRow,
    JobSearchRow,
    OtherActivityRow,
    SubmitMode,
)
from app.schemas.common import (
    ErrorCode,
    FieldSource,
    FormName,
    FormUpdate,
    JsonPatchOp,
    UpdatesRead,
)
from app.schemas.forms.recognition import RecognitionData
from app.schemas.rounds import ApplicationStatus, WarningId
from app.services import accounts as account_service
from app.services import rounds as round_service
from app.services.accounts import AccountContext
from app.services.profile import read_profile_display

CURRENT = "current"
ROUND_NOT_FOUND_MESSAGE = "그 회차의 신청서가 없어요."


def find_round(db: Session, user_id: uuid.UUID, round_ref: str, today: date):
    rounds = repo.list_rounds(db, user_id)
    if round_ref == CURRENT:
        return round_service.current_round(rounds, today), rounds
    found = next((r for r in rounds if r.round_no == int(round_ref)), None)
    if found is None:
        raise NotFoundError(message=ROUND_NOT_FOUND_MESSAGE)
    return found, rounds


def _previous_answers(db: Session, rounds: list, round_no: int) -> dict | None:
    """이번 회차 바로 전까지 제출한 회차 중 가장 최근 신청서의 답."""
    for r in reversed([r for r in rounds if r.round_no < round_no]):
        previous = repo.get_application(db, r.round_id)
        if previous is not None and previous.status == ApplicationStatus.SUBMITTED:
            return previous.data
    return None


def read_application(
    db: Session, account: AccountContext, round_ref: str, now: datetime
) -> ApplicationRead:
    """신청서와 지금 시각(KST) 기준 제출 방식·제출 전 확인을 돌려줍니다 (F-23·F-26)."""
    target, rounds = find_round(db, account.user_id, round_ref, now.date())
    application = repo.get_application(db, target.round_id)
    if application is None:
        raise NotFoundError(message=ROUND_NOT_FOUND_MESSAGE)
    context = round_service.evaluate_round(db, account.user_id, target, rounds, now.date())
    check = context.result

    data = rules.carry_previous_answers(
        application.data, _previous_answers(db, rounds, target.round_no)
    )
    statuses = {a.activity_id: a.status for a in check.activities}
    activities = rules.build_form_activities(context.inputs, statuses)
    # 증빙이 필요한데 없는 인정 활동 수 (회차 점검 W5와 같은 기준)
    counted_ids = {row["activity_id"] for row in activities.job_search + activities.other}
    evidence_missing = sum(
        1
        for w in check.warnings
        if w.id == WarningId.NO_EVIDENCE and counted_ids.intersection(w.activity_ids)
    )
    blocking, warnings = rules.checklist(
        data,
        activities.job_search,
        check.remaining,
        check.remaining_job_search,
        evidence_missing,
    )
    locked = rules.locked_reason(data)
    mode = rules.submit_mode(now, target.recognition_date, target.attendance_required)
    return ApplicationRead(
        round=target.round_no,
        status=application.status,
        lock_version=application.lock_version,
        period_start=target.period_start,
        period_end=target.period_end,
        recognition_date=target.recognition_date,
        attendance_required=target.attendance_required,
        required_activities=check.required,
        required_job_search=check.required_job_search,
        data=RecognitionData.model_validate(data),
        job_search_rows=[JobSearchRow.model_validate(row) for row in activities.job_search],
        other_rows=[OtherActivityRow.model_validate(row) for row in activities.other],
        excluded_rows=[ExcludedRow.model_validate(row) for row in activities.excluded],
        checklist=Checklist(
            blocking=[ChecklistItem(**item) for item in blocking],
            warnings=[ChecklistItem(**item) for item in warnings],
        ),
        submit_mode=SubmitMode(mode),
        can_submit=rules.can_submit(mode, blocking, locked),
        locked_reason=locked,
        profile_display=read_profile_display(db, account.user_id),
    )


# ── 고치기 · 제출 (F-27, 설계 3.6) ─────────────────────────────────────────────

SUBMIT_PATHS = {"/status", "/submit_mode", "/attend_items"}
ATTEND_ITEMS = {"id_card", "eligibility_card"}
SUBMITTABLE_MODES = {SubmitMode.SEND, SubmitMode.ATTEND}
ATTEND_ITEMS_MESSAGE = "신분증과 수급자격증을 챙겼는지 체크해 주세요."
SUBMIT_VALUE_MESSAGE = "제출 방식은 글자로, 준비물은 글자 목록으로 보내 주세요."
LOCKED_MESSAGE = "이미 제출한 신청서예요. 고칠 게 있으면 고용센터에 문의해 주세요."


def _writable(db: Session, account: AccountContext, round_ref: str, now: datetime):
    """고칠 수 있는 신청서인지 확인하고 (회차, 신청서 행)을 돌려줍니다."""
    # 수급이 끝난 계정은 신청서를 고칠 수 없습니다 (F-33 완료 기준).
    account_service.ensure_not_ended(db, account.user_id)
    target, _ = find_round(db, account.user_id, round_ref, now.date())
    # 대화의 답 저장과 제출이 겹쳐도 나중 저장이 앞 답을 덮지 않게 행을 잠급니다.
    application = repo.get_application(db, target.round_id, for_update=True)
    if application is None:
        raise NotFoundError(message=ROUND_NOT_FOUND_MESSAGE)
    if now.date() > target.recognition_date:
        raise ConflictError(code=ErrorCode.ROUND_CLOSED)
    if application.status == ApplicationStatus.SUBMITTED:
        raise ConflictError(code=ErrorCode.APPLICATION_LOCKED, message=LOCKED_MESSAGE)
    return target, application


def patch_application(
    db: Session,
    account: AccountContext,
    round_ref: str,
    patch: list[JsonPatchOp],
    if_match: str | None,
    now: datetime,
) -> UpdatesRead:
    """신청서 PATCH. 제출(/status·/submit_mode·/attend_items)만 받습니다.

    신청서 칸은 모두 본인 답변이라 직접 고칠 수 없고(422 USER_ANSWER_ONLY),
    대화의 본인 답변 기록(`record_user_answer`)으로만 채웁니다.
    답은 받을 때마다 바로 저장되므로 임시저장은 따로 없습니다.
    """
    target, application = _writable(db, account, round_ref, now)
    check_if_match(if_match, application.lock_version)
    submit_ops = [op for op in patch if op.path in SUBMIT_PATHS]
    if not submit_ops:
        raise UnprocessableError(code=ErrorCode.USER_ANSWER_ONLY)
    if len(submit_ops) != len(patch):
        raise UnprocessableError(code=ErrorCode.STATUS_WITH_FIELDS)
    # 제출 칸은 값을 정하는 연산(replace)으로만 바꿉니다. remove·add로는 제출하지 않습니다.
    if any(op.op != "replace" for op in submit_ops):
        raise UnprocessableError(message="제출은 replace 연산으로 보내 주세요.")
    return _submit(db, account, target, application, submit_ops, now)


def _submit(db, account, target, application, ops: list[JsonPatchOp], now: datetime):
    values = {op.path: op.value for op in ops}
    if values.get("/status") != ApplicationStatus.SUBMITTED:
        raise UnprocessableError(message="제출은 /status를 submitted로 보내 주세요.")
    requested = values.get("/submit_mode")
    attend_items = values.get("/attend_items")
    if not isinstance(requested, str) or not (
        attend_items is None
        or (isinstance(attend_items, list) and all(isinstance(i, str) for i in attend_items))
    ):
        raise UnprocessableError(message=SUBMIT_VALUE_MESSAGE)
    current = read_application(db, account, str(target.round_no), now)
    # 서버가 지금 시각으로 정한 방식과 다르거나(예: 인정일 전 preview에서 send)
    # 막는 항목이 남으면 409
    if (
        requested not in SUBMITTABLE_MODES
        or requested != current.submit_mode
        or not current.can_submit
    ):
        raise ConflictError(code=ErrorCode.CANNOT_SUBMIT)
    if requested == SubmitMode.ATTEND and set(attend_items or []) != ATTEND_ITEMS:
        raise ConflictError(code=ErrorCode.CANNOT_SUBMIT, message=ATTEND_ITEMS_MESSAGE)
    # 제출은 상태만 바꿉니다. 본인 답변(data)은 지우지 않습니다 (점검 9).
    application.status = ApplicationStatus.SUBMITTED
    application.submit_mode = requested
    application.submitted_at = now
    application.lock_version += 1
    db.commit()
    entry = account_service.read_account(db, account, now.date()).entry
    return UpdatesRead(
        updates=[
            _replaced("/status", ApplicationStatus.SUBMITTED),
            _replaced("/submit_mode", requested),
        ],
        entry=entry.model_dump(mode="json"),
    )


def _replaced(path: str, value: object) -> FormUpdate:
    return FormUpdate(form=FormName.APPLICATION, path=path, op="replace", value=value)


def record_user_answer(
    db: Session,
    account: AccountContext,
    round_ref: str,
    patch: list[JsonPatchOp],
    now: datetime,
) -> list[FormUpdate]:
    """본인 답변 칸을 바로 저장합니다(대화 턴의 `record_user_answer` 도구가 부름, F-24·F-27).

    답한 날(answered_on)을 남기고 lock_version을 올립니다. 제출 뒤·지난 회차는 409입니다.
    """
    _, application = _writable(db, account, round_ref, now)
    data, updates = apply_patch(
        application.data, patch, form=FormName.APPLICATION, source=FieldSource.USER_ANSWER
    )
    for op in patch:
        _stamp_answered_on(data, op.path, now.date())
    application.data = data
    application.lock_version += 1
    db.commit()
    return updates


def _stamp_answered_on(data: dict, path: str, answered_on: date) -> None:
    node: object = data
    for key in path.strip("/").split("/"):
        if not isinstance(node, dict) or key not in node:
            return
        node = node[key]
    if isinstance(node, dict) and "value" in node:
        node["answered_on"] = answered_on.isoformat()
