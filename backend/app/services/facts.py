"""내 정보 창: 작성한 서류·절차 상태·내가 답한 내용을 모아 보여 주고, 내 답을 한 줄씩
지웁니다 (F-31).

따로 저장하는 테이블은 없습니다. 이력서와 지금 회차 신청서에서 사용자가 답한 칸
(source=user_answer)을 모은 보기입니다. 지우기는 그 칸을 답변 필요 상태로 되돌리는 것이고,
서류·절차 줄은 지울 수 없습니다.
"""

from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.repositories import accounts as repo
from app.rules import application as form_rules
from app.rules import resume as resume_rules
from app.schemas.common import (
    ErrorCode,
    FieldSource,
    FieldStatus,
    FormName,
    FormUpdate,
    UpdatesRead,
)
from app.schemas.facts import FactGroup, FactList, FactRead
from app.schemas.procedure import Stage
from app.schemas.resume import FieldWrite, ResumeStatus
from app.schemas.rounds import RoundStatus
from app.services import accounts as account_service
from app.services import resume as resume_service
from app.services.accounts import AccountContext
from app.services.application import (
    CURRENT,
    find_round,
    previous_answers,
    writable_application,
)

FACT_NOT_FOUND_MESSAGE = "지울 줄을 찾지 못했어요."
# shortcut: #179의 PatchOpName이 develop에 들어오면 PatchOpName.REPLACE로 바꿉니다.
REPLACE_OP = "replace"
ID_SEP = "."
PATH_SEP = "/"

# 지울 수 없는 줄 (서류·절차)
RESUME_STATUS_ID = "resume.status"
STAGE_ID = "procedure.stage"
NEXT_DATE_ID = "procedure.next_recognition_date"
# 신청서 내 답 줄 → 지우면 답변 필요로 돌릴 칸들
APPLICATION_PREFIX = "application"
CREDIT_ID = "application.credit"
NOTIFICATION_ID = "application.notification_method"
CREDIT_KEYS = ("application", "notice_method", "auto_payment", "income_asset_consent")
APPLICATION_FACT_PATHS = {
    CREDIT_ID: [f"/credit/{key}" for key in CREDIT_KEYS],
    NOTIFICATION_ID: ["/notification_method"],
}
RESUME_PREFIX = "resume"

# 서비스가 저장하지 않는 정보 (상세기획 2-0.5)
NOT_STORED = [
    "주민등록번호",
    "이름·연락처·주소·이메일",
    "계좌번호",
    "사업장 이메일·전화번호",
    "서류·음성 원본",
    "건강 관련 이직 사유",
]

STAGE_LABEL = {
    Stage.JOB_REGISTRATION: "구직등록",
    Stage.EDUCATION: "온라인 교육",
    Stage.ELIGIBILITY_APPLICATION: "수급자격 신청",
    Stage.ELIGIBILITY_APPLIED: "수급자격 신청 완료",
    Stage.RECOGNITION: "실업인정",
    Stage.ENDED: "수급 종료",
}
RESUME_STATUS_LABEL = {ResumeStatus.SAVED: "저장 완료", ResumeStatus.DRAFT: "작성 중"}
# 신청서 답 코드 → 고용24 화면 글자
CREDIT_LABEL = {
    "application": {"wish": "희망함", "not_wish": "희망하지 않음", "not_applicable": "해당 없음"},
    "notice_method": {"electronic": "전자고지", "mail": "우편"},
    "auto_payment": {"wish": "자동이체 희망함", "not_wish": "자동이체 희망하지 않음"},
    "income_asset_consent": {
        "agree": "재산 소득 확인 동의함",
        "disagree": "재산 소득 확인 동의하지 않음",
    },
}
NOTIFICATION_LABEL = {"sms": "휴대전화 문자메시지", "email": "전자우편", "mail": "우편"}
# 이력서 칸 이름 → 화면 이름. 없는 칸은 칸 이름 그대로 보입니다.
RESUME_FIELD_LABEL = {
    "resume_title": "이력서 제목",
    "education_level": "학력",
    "graduation_status": "졸업상태",
    "school_name": "학교명",
    "major": "전공",
    "occupation": "직종",
    "experience_type": "경력여부",
    "desired_job_description": "희망직무내용",
    "desired_regions": "희망근무지역",
    "desired_salary": "희망임금",
    "employment_contract_type": "고용형태",
    "military_alternative": "병역대체",
    "company_name": "회사명",
    "start_date": "시작",
    "end_date": "끝",
    "position": "직급/직책",
    "main_duties": "주요 직무",
    "monthly_salary": "급여(월)",
    "certificate_name": "자격면허",
    "can_drive": "운전가능",
    "owns_vehicle": "차량소지",
}


def list_facts(db: Session, account: AccountContext, today: date) -> FactList:
    items = [*_fixed_rows(db, account, today), *_application_rows(db, account, today)]
    items += _resume_rows(db, account)
    return FactList(items=items, total=len(items), not_stored=NOT_STORED)


def delete_fact(db: Session, account: AccountContext, fact_id: str, now: datetime) -> UpdatesRead:
    if fact_id in (RESUME_STATUS_ID, STAGE_ID, NEXT_DATE_ID):
        raise ConflictError(code=ErrorCode.FACT_NOT_DELETABLE)
    repo.lock_user(db, account.user_id)
    if fact_id in APPLICATION_FACT_PATHS:
        return _withdraw_application(db, account, APPLICATION_FACT_PATHS[fact_id], now)
    if fact_id.startswith(RESUME_PREFIX + ID_SEP):
        return _clear_resume(db, account, fact_id, now)
    raise NotFoundError(message=FACT_NOT_FOUND_MESSAGE)


# ── 보기 ────────────────────────────────────────────────────────────


def _row(fact_id: str, group: FactGroup, label: str, value: str | None, **extra) -> FactRead:
    return FactRead(
        fact_id=fact_id,
        group=group,
        label=label,
        value=value,
        is_deletable=group == FactGroup.FACTS,
        **extra,
    )


def _fixed_rows(db: Session, account: AccountContext, today: date) -> list[FactRead]:
    rows = []
    resume = repo.get_resume(db, account.user_id)
    if resume is not None:
        status = RESUME_STATUS_LABEL[ResumeStatus(resume.status)]
        rows.append(_row(RESUME_STATUS_ID, FactGroup.RESUME, "이력서", status))
    procedure = account_service.read_procedure(db, account.user_id, today)
    rows.append(_row(STAGE_ID, FactGroup.PROCEDURE, "절차 단계", STAGE_LABEL[procedure.stage]))
    rounds = account_service.read_rounds(db, account.user_id, today)
    current = next((r for r in rounds if r.status == RoundStatus.CURRENT), None)
    if current is not None:
        place = " · 고용센터 출석" if current.attendance_required else ""
        text = f"{current.round}차 · {current.recognition_date:%m.%d}{place}"
        rows.append(_row(NEXT_DATE_ID, FactGroup.PROCEDURE, "다음 실업인정일", text))
    return rows


def _current_application_data(
    db: Session, account: AccountContext, today: date
) -> dict[str, Any] | None:
    """화면과 같게, 이번 회차에 답이 없으면 지난 회차 답을 불러온 값입니다."""
    try:
        target, rounds = find_round(db, account.user_id, CURRENT, today)
    except NotFoundError:
        return None
    application = repo.get_application(db, target.round_id)
    if application is None:
        return None
    previous = previous_answers(db, rounds, target.round_no)
    return form_rules.carry_previous_answers(application.data, previous)


def _answered(node: Any) -> bool:
    return (
        isinstance(node, dict)
        and node.get("source") == FieldSource.USER_ANSWER
        and node.get("value") not in (None, "", [])
    )


def _application_rows(db: Session, account: AccountContext, today: date) -> list[FactRead]:
    data = _current_application_data(db, account, today)
    if data is None:
        return []
    rows = []
    credit = data.get("credit") or {}
    answered = [(k, credit[k]) for k in CREDIT_KEYS if _answered(credit.get(k))]
    if answered:
        text = " · ".join(CREDIT_LABEL[k].get(n["value"], n["value"]) for k, n in answered)
        on = max((n.get("answered_on") for _, n in answered if n.get("answered_on")), default=None)
        rows.append(_row(CREDIT_ID, FactGroup.FACTS, "실업크레딧 답", text, answered_on=on))
    method = data.get("notification_method")
    if _answered(method):
        text = NOTIFICATION_LABEL.get(method["value"], method["value"])
        rows.append(
            _row(
                NOTIFICATION_ID,
                FactGroup.FACTS,
                "지급 결정 통지 방법",
                text,
                answered_on=method.get("answered_on"),
            )
        )
    return rows


def _resume_rows(db: Session, account: AccountContext) -> list[FactRead]:
    resume = repo.get_resume(db, account.user_id)
    if resume is None:
        return []
    data = resume_service.read_resume_data(resume)
    return [
        _row(
            RESUME_PREFIX + path.replace(PATH_SEP, ID_SEP),
            FactGroup.FACTS,
            _resume_label(path),
            _text(field.value),
            answered_on=field.answered_on,
        )
        for path, field in resume_rules.form_fields(data)
        if field.source == FieldSource.USER_ANSWER and resume_rules.is_filled(field)
    ]


def _resume_label(path: str) -> str:
    name = path.rsplit(PATH_SEP, 1)[-1]
    return RESUME_FIELD_LABEL.get(name, name)


def _text(value: Any) -> str | None:
    """값을 한 줄 글로. 직종·지역처럼 {name} 모양이면 이름만 씁니다."""
    if value is None:
        return None
    if isinstance(value, dict):
        return str(value.get("name") or value.get("amount") or "")
    if isinstance(value, list):
        return ", ".join(_text(v) or "" for v in value)
    return str(value)


# ── 지우기 ──────────────────────────────────────────────────────────


def _withdraw_application(
    db: Session, account: AccountContext, paths: list[str], now: datetime
) -> UpdatesRead:
    """신청서 칸을 '사용자가 거둬들임'(rejected)으로 둡니다.

    지난 회차 답을 다시 불러오지 않게 빈 칸(missing)이 아니라 rejected로 둡니다.
    """
    _, application = writable_application(db, account, CURRENT, now)
    data = {**application.data}
    updates = []
    for path in paths:
        *parents, last = path.strip(PATH_SEP).split(PATH_SEP)
        node = data
        for key in parents:
            node[key] = {**(node.get(key) or {})}
            node = node[key]
        node[last] = {
            "value": None,
            "status": FieldStatus.REJECTED,
            "source": FieldSource.USER_ANSWER,
        }
        updates.append(
            FormUpdate(
                form=FormName.APPLICATION,
                path=path,
                op=REPLACE_OP,
                value=None,
                status=FieldStatus.REJECTED,
                source=FieldSource.USER_ANSWER,
            )
        )
    application.data = data
    application.lock_version += 1
    db.commit()
    return UpdatesRead(updates=updates)


def _clear_resume(db: Session, account: AccountContext, fact_id: str, now: datetime) -> UpdatesRead:
    path = PATH_SEP + fact_id.removeprefix(RESUME_PREFIX + ID_SEP).replace(ID_SEP, PATH_SEP)
    resume = repo.get_resume(db, account.user_id)
    fields = (
        dict(resume_rules.form_fields(resume_service.read_resume_data(resume))) if resume else {}
    )
    field = fields.get(path)
    if field is None or field.source != FieldSource.USER_ANSWER:
        raise NotFoundError(message=FACT_NOT_FOUND_MESSAGE)
    result = resume_service.save_resume_fields(
        db,
        account.user_id,
        [FieldWrite(path=path, value=None, status=FieldStatus.MISSING)],
        today=now.date(),
    )
    return UpdatesRead(updates=result.updates)
