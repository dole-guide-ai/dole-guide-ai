"""이력서 조회·칸 쓰기·저장 서비스입니다 (F-14·F-15).

AI 도구가 뽑은 값을 칸마다 상태·출처와 함께 저장하고, 자동 값(재직여부·최종학력·경력 합계)을
다시 계산한 뒤 바뀐 칸 목록과 다음 질문을 돌려줍니다. 계산은 모두 app/rules/resume.py가 합니다.
REST의 조회·직접 고치기·저장(상세기획 2-1.6)도 여기서 합니다.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import json_patch
from app.core.clock import KST
from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.core.etag import check_if_match
from app.repositories import accounts as repo
from app.rules import resume as rules
from app.schemas.accounts import EntryMessage
from app.schemas.common import (
    ErrorCode,
    FieldSource,
    FieldStatus,
    FormName,
    FormUpdate,
    JsonPatchOp,
    PatchErrorType,
    PatchOpName,
    UpdatesRead,
)
from app.schemas.forms import resume as resume_form
from app.schemas.procedure import Stage
from app.schemas.resume import Completeness, FieldWrite, ResumeRead, ResumeStatus
from app.services import accounts as account_service
from app.services.accounts import AccountContext, seed_resume
from app.services.profile import read_profile_display

# 저장 뒤 첫 안내 (상세기획 2-1.6). E7a(새로 씀)와 E7b(예전 이력서 최신화) 문장이 다릅니다.
SAVED_TEXT = {
    "E7a": "이력서를 저장해서 구직등록이 끝났어요. 다음은 수급자격 신청자 온라인 교육이에요. "
    "약 1시간이고, 다 들으시면 아래 ‘교육 다 들었어요’를 눌러 알려 주세요.",
    "E7b": "이력서를 최신화해 저장했어요. 구직등록이 끝났어요. 다음은 온라인 교육이에요. "
    "다 들으시면 아래 ‘교육 다 들었어요’를 눌러 알려 주세요.",
}
# 고용24에 옮겨 적을 때 안내. 이 이력서에 해당하는 줄만 붙입니다.
HINT_HEAD = "고용24에 옮겨 적으실 때 참고하세요."
HINT_JOB_SKILLS = "· 직무능력은 고용24에서 '직무능력 자동 추천'으로 골라 주세요."
HINT_SALARY = "· 희망임금은 금액 앞 선택 상자에서 월급 단위를 고르세요."
HINT_NAME_ONLY = "· 희망 직종 '{name}'은 고용24 직종 검색에서 가장 가까운 것을 골라 주세요."
HINT_PERIOD = "· 총 근무기간은 경력을 다 넣으면 고용24가 자동으로 계산해요."
HINT_GPA = "· 학점은 만점 기준(4.5 등)을 먼저 고르고 넣어 주세요."


@dataclass(frozen=True)
class ResumeWriteResult:
    updates: list[FormUpdate]
    next_question: rules.ResumeQuestion
    issues: list[rules.ResumeIssue]


def save_resume_fields(
    db: Session, user_id: uuid.UUID, writes: list[FieldWrite], *, today: date
) -> ResumeWriteResult:
    procedure = repo.get_procedure(db, user_id)
    if procedure is None:
        raise NotFoundError(code=ErrorCode.ACCOUNT_NOT_FOUND)
    resume = repo.get_resume(db, user_id)
    if resume is None:
        resume = repo.Resume(
            user_id=user_id,
            schema_version=resume_form.SCHEMA_VERSION,
            status="draft",
            data=resume_form.ResumeData().model_dump(mode="json"),
        )
        repo.add_all(db, [resume])

    before = resume_form.ResumeData.model_validate(_upgrade_legacy(resume.data))
    raw = before.model_dump(mode="json")
    for index, w in enumerate(writes):
        if not _shape_ok(w):
            raise UnprocessableError(
                "값 모양이 맞지 않아요.",
                details=[{"field": f"writes[{index}]", "type": PatchErrorType.BAD_SHAPE}],
            )
        json_patch.set_field(raw, w.path, w.model_dump(mode="json", exclude={"path"}))
    try:
        written = resume_form.ResumeData.model_validate(raw)
    except ValidationError:
        # 오류에 입력값을 넣지 않고 칸 이름이 틀렸다는 것만 알립니다.
        raise UnprocessableError("고칠 칸을 찾지 못했어요.") from None

    data = rules.derive_resume_values(written, procedure.separation_date)
    issues = rules.check_resume(data, procedure.separation_date, today)
    too_many = [i.path for i in issues if i.code == "too_many"]
    if too_many:
        raise UnprocessableError(
            "고용24는 3개까지만 넣을 수 있어요.",
            details=[{"field": p, "type": PatchErrorType.TOO_MANY} for p in too_many],
        )

    resume.data = data.model_dump(mode="json")
    # 저장한 이력서를 고치면 다시 저장할 때까지 초안입니다 (5/5가 깨질 수 있음).
    resume.status = ResumeStatus.DRAFT
    resume.lock_version += 1
    db.commit()

    completeness = rules.resume_completeness(
        data, outdated=_outdated(resume, procedure.separation_date)
    ).model_dump()
    old = dict(rules.form_fields(before))
    updates = [
        FormUpdate(
            form=FormName.RESUME,
            path=path,
            op="replace" if path in old else "add",
            value=f.value,
            status=f.status,
            source=f.source,
            transformed=f.transformed,
            evidence=f.evidence,
            completeness=completeness,
        )
        for path, f in rules.form_fields(data)
        if old.get(path) != f
    ]
    question = rules.next_resume_question(
        data, entry_branch=_branch(data), separation_date=procedure.separation_date
    )
    return ResumeWriteResult(updates, question, issues)


def read_resume(db: Session, account: AccountContext) -> ResumeRead:
    """이력서가 아직 없으면(박진수) 빈 초안을 lock_version 0으로 돌려줍니다."""
    procedure = _procedure_or_404(db, account.user_id)
    resume = repo.get_resume(db, account.user_id)
    data = read_resume_data(resume)
    question = rules.next_resume_question(
        data, entry_branch=_branch(data), separation_date=procedure.separation_date
    )
    outdated = _outdated(resume, procedure.separation_date)
    return ResumeRead(
        status=resume.status if resume else ResumeStatus.DRAFT,
        lock_version=resume.lock_version if resume else 0,
        data=data,
        completeness=Completeness(filled=rules.resume_completeness(data, outdated=outdated).filled),
        next_question=question.id,
        can_save=rules.can_save_resume(data, outdated=outdated),
        profile_display=read_profile_display(db, account.user_id),
    )


def patch_resume(
    db: Session,
    account: AccountContext,
    patch: list[JsonPatchOp],
    if_match: str | None,
    now: datetime,
) -> UpdatesRead:
    """직접 고치기는 칸마다 confirmed·direct로 쓰고, `/status`는 저장(saved)·다시 고치기(draft)."""
    # 같은 버전을 읽은 두 PATCH가 모두 통과하지 않게 계정 행을 잠근 뒤 버전을 봅니다.
    repo.lock_user(db, account.user_id)
    resume = repo.get_resume(db, account.user_id)
    check_if_match(if_match, resume.lock_version if resume else 0)
    status_ops = [op for op in patch if op.path == "/status"]
    if status_ops:
        if len(patch) != 1 or status_ops[0].op != "replace":
            raise UnprocessableError(code=ErrorCode.STATUS_WITH_FIELDS)
        if status_ops[0].value == ResumeStatus.SAVED:
            return _save(db, account, now)
        if status_ops[0].value == ResumeStatus.DRAFT and resume is not None:
            resume.status = ResumeStatus.DRAFT
            resume.lock_version += 1
            db.commit()
            return UpdatesRead(updates=[_status_update(ResumeStatus.DRAFT)])
        raise UnprocessableError("저장은 /status를 saved로 보내 주세요.")

    for index, op in enumerate(patch):
        if op.op != PatchOpName.REMOVE and not _date_ok(op.path, op.value):
            raise UnprocessableError(
                DATE_FORMAT_MESSAGE,
                details=[{"field": f"patch[{index}]", "type": PatchErrorType.DATE_FORMAT}],
            )
    # shortcut: 항목 통째로 지우기(remove /careers/c1)는 칸 쓰기로 표현할 수 없어 아직 422입니다.
    writes = [
        FieldWrite(
            path=op.path,
            value=None if op.op == "remove" else op.value,
            status=FieldStatus.MISSING if op.op == "remove" else FieldStatus.CONFIRMED,
            source=FieldSource.DIRECT,
        )
        for op in patch
    ]
    result = save_resume_fields(db, account.user_id, writes, today=now.date())
    return UpdatesRead(updates=result.updates)


def _save(db: Session, account: AccountContext, now: datetime) -> UpdatesRead:
    procedure = _procedure_or_404(db, account.user_id)
    resume = repo.get_resume(db, account.user_id)
    data = read_resume_data(resume)
    if resume is None or not rules.can_save_resume(
        data, outdated=_outdated(resume, procedure.separation_date)
    ):
        raise ConflictError(code=ErrorCode.RESUME_NOT_READY)
    branch = _branch(data)
    resume.status = ResumeStatus.SAVED
    resume.saved_at = now
    resume.lock_version += 1
    # 다시 저장(교육 단계 이후)은 단계를 그대로 둡니다.
    if procedure.stage == Stage.JOB_REGISTRATION:
        procedure.stage = Stage.EDUCATION
        procedure.lock_version += 1
    db.commit()

    entry = account_service.read_account(db, account, now.date()).entry
    entry.messages[:0] = [
        EntryMessage(template_id=f"T-SAVE-{branch}", text=SAVED_TEXT[branch]),
        EntryMessage(template_id="T-WORK24-HINT", text=work24_hint(data)),
    ]
    return UpdatesRead(
        updates=[_status_update(ResumeStatus.SAVED)], entry=entry.model_dump(mode="json")
    )


def work24_hint(data: resume_form.ResumeData) -> str:
    """고용24 입력 안내 중 이 이력서에 해당하는 줄만 모읍니다."""
    prefs = data.job_preferences
    lines = [HINT_HEAD, HINT_JOB_SKILLS]
    if rules.is_filled(prefs.desired_salary):
        lines.append(HINT_SALARY)
    for o in prefs.desired_occupations:
        occ = rules.occupation_value(o.occupation)
        if occ.get("status") == resume_form.OccupationStatus.NAME_ONLY:
            lines.append(HINT_NAME_ONLY.format(name=occ.get("name")))
    if data.careers:
        lines.append(HINT_PERIOD)
    if any(rules.is_filled(e.gpa) for e in data.education):
        lines.append(HINT_GPA)
    return "\n".join(lines)


# 직접 입력한 날짜는 고용24 칸 형식(연-월, 자격 취득일만 연-월-일도)이어야 저장합니다 (F-12).
DATE_FORMAT_MESSAGE = "날짜는 2004-03처럼 연-월로 넣어 주세요."
_YM = re.compile(r"\d{4}-(0[1-9]|1[0-2])", re.ASCII)
_YMD = re.compile(r"\d{4}-(0[1-9]|1[0-2])(-\d{2})?", re.ASCII)
YM_LENGTH = len("YYYY-MM")
DATE_FIELD_SUFFIX = "_date"
# 연-월-일까지 받는 칸 (자격 취득일)
FULL_DATE_FIELDS = ("acquired_date",)


def _date_ok(path: str, value: Any) -> bool:
    if not path.endswith(DATE_FIELD_SUFFIX) or value is None:
        return True
    pattern = _YMD if path.rsplit("/", 1)[-1] in FULL_DATE_FIELDS else _YM
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        return False
    if len(value) == YM_LENGTH:
        return True
    try:  # 2011-02-31처럼 달력에 없는 날은 막습니다.
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _procedure_or_404(db: Session, user_id: uuid.UUID):
    procedure = repo.get_procedure(db, user_id)
    if procedure is None:
        raise NotFoundError(code=ErrorCode.ACCOUNT_NOT_FOUND)
    return procedure


def confirm_field(db: Session, user_id: uuid.UUID, path: str, *, today: date) -> ResumeWriteResult:
    """확인 질문에 "네, 맞아요"라고 한 칸을 확정합니다 (2-1.4, 확인 필요 → 확정).

    값 · 출처 · 근거는 그대로 두고 상태만 confirmed로 바꿉니다. 없는 칸이면 422입니다.
    """
    data = read_resume_data(repo.get_resume(db, user_id))
    field = dict(rules.form_fields(data)).get(path)
    if field is None:
        raise UnprocessableError("확인할 칸을 찾지 못했어요.")
    write = FieldWrite(
        path=path,
        value=field.value,
        status=FieldStatus.CONFIRMED,
        source=field.source or FieldSource.USER_ANSWER,
        transformed=False,
        evidence=field.evidence.model_dump(mode="json") if field.evidence else None,
    )
    return save_resume_fields(db, user_id, [write], today=today)


def next_question(db: Session, user_id: uuid.UUID, *, doc_failed: bool = False):
    """지금 이력서에서 다음에 물을 질문 (대화 턴이 부름, F-14). 절차 상태가 없으면 None."""
    procedure = repo.get_procedure(db, user_id)
    if procedure is None:
        return None
    data = read_resume_data(repo.get_resume(db, user_id))
    return rules.next_resume_question(
        data,
        entry_branch=_branch(data),
        separation_date=procedure.separation_date,
        doc_failed=doc_failed,
    )


def read_resume_data(resume: repo.Resume | None) -> resume_form.ResumeData:
    if resume is None:
        return resume_form.ResumeData()
    return resume_form.ResumeData.model_validate(_upgrade_legacy(resume.data))


def _outdated(resume: repo.Resume | None, separation_date: date) -> bool:
    if resume is not None and resume.status == ResumeStatus.SAVED and resume.saved_at is None:
        return (
            True  # 저장일을 모르는 저장 이력서는 예전 것으로 봅니다(accounts._resume_status와 같음)
        )
    saved_on = resume.saved_at.astimezone(KST).date() if resume and resume.saved_at else None
    return rules.saved_before_separation(saved_on, separation_date)


def _branch(data: resume_form.ResumeData) -> str:
    """예전 이력서(seed) 값이 남아 있으면 최신화 중(E7b)입니다."""
    seeded = any(f.source == FieldSource.SEED for _, f in rules.form_fields(data))
    return "E7b" if seeded else "E7a"


def _status_update(status: ResumeStatus) -> FormUpdate:
    return FormUpdate(form=FormName.RESUME, path="/status", op="replace", value=status)


def _shape_ok(w: FieldWrite) -> bool:
    """직종은 {name, ...}, 희망 지역은 [{name, ...}]여야 규칙 함수가 읽을 수 있습니다."""
    if w.value is None:
        return True
    if w.path.endswith("/occupation"):
        return isinstance(w.value, dict) and isinstance(w.value.get("name"), str)
    if w.path == "/job_preferences/desired_regions":
        return isinstance(w.value, list) and all(
            isinstance(r, dict) and isinstance(r.get("name"), str) for r in w.value
        )
    return True


def _upgrade_legacy(data: dict[str, Any]) -> dict[str, Any]:
    """#166 이전 구조(title, level·is_final, 값만 있는 항목)를 지금 구조로 바꿉니다.

    예전에는 이력서를 쓰는 API가 없어 예전 행은 모두 seed에서 만든 것이라 seed 적재와 같은
    방식으로 감쌉니다. 두 구조가 같은 schema_version이라 `title` 칸 유무로 구분합니다.
    """
    if "title" not in data:
        return data
    rename = {"level": "education_level", "is_final": "is_highest_education"}
    prefs = data.get("job_preferences") or {}
    plain = {
        "resume_title": (data["title"] or {}).get("value"),
        "education": [
            {rename.get(k, k): v for k, v in e.items()} for e in data.get("education", [])
        ],
        "job_preferences": {
            "desired_occupations": [
                {"item_id": f"occ_{i:03d}", "occupation": o}
                for i, o in enumerate(prefs.get("desired_occupations") or [], 1)
            ],
            "desired_regions": [
                {"code": None, "name": r} for r in prefs.get("desired_regions") or []
            ],
        },
        "careers": data.get("careers", []),
        "certifications": data.get("certifications", []),
    }
    status = (data["title"] or {}).get("status") or "extracted"
    return seed_resume(plain, status).model_dump(mode="json")
