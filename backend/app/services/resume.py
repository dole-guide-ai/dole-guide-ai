"""대화 턴이 이력서 칸에 값을 쓰는 서비스입니다 (F-14).

AI 도구가 뽑은 값을 칸마다 상태·출처와 함께 저장하고, 자동 값(재직여부·최종학력·경력 합계)을
다시 계산한 뒤 바뀐 칸 목록과 다음 질문을 돌려줍니다. 계산은 모두 app/rules/resume.py가 합니다.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core import json_patch
from app.core.errors import NotFoundError, UnprocessableError
from app.repositories import accounts as repo
from app.rules import resume as rules
from app.schemas.common import ErrorCode, FieldSource, FormName, FormUpdate
from app.schemas.forms import resume as resume_form
from app.schemas.resume import FieldWrite


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

    before = resume_form.ResumeData.model_validate(resume.data)
    raw = before.model_dump(mode="json")
    for w in writes:
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
            details=[{"field": p, "reason": "too_many"} for p in too_many],
        )

    resume.data = data.model_dump(mode="json")
    resume.lock_version += 1
    db.commit()

    completeness = rules.resume_completeness(data).model_dump()
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
    # 예전 이력서(seed) 값이 남아 있으면 최신화 중(E7b)입니다.
    seeded = any(f.source == FieldSource.SEED for _, f in rules.form_fields(data))
    question = rules.next_resume_question(
        data, entry_branch="E7b" if seeded else "E7a", separation_date=procedure.separation_date
    )
    return ResumeWriteResult(updates, question, issues)
