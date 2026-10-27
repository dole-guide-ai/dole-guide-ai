"""고용24 불러오기(모의) 목록과 고른 항목 넣기 (F-10, 설계 3.7).

목록은 계정에 입장할 때 seed에서 복사한 work24_imports 행이고, 실제 고용24에는 연결하지 않습니다.
고른 항목을 넣으면 입사지원은 구직활동(출처 import)으로, 경력·자격은 이력서 칸(출처 import)으로
들어가고 is_recorded가 true가 됩니다. 이미 넣은 항목은 다시 넣지 않습니다.
대화로 먼저 적은 같은 회사·자격증이 있으면 새 항목을 만들지 않고 그 항목을 채웁니다
(대화와 같은 기준, rules/resume/items).
"""

from datetime import date

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models import Work24Import
from app.repositories import imports as import_repo
from app.rules import imports as import_rules
from app.rules.resume.items import ItemPicker
from app.schemas.activities import ActivityCreate, ActivityRoute
from app.schemas.common import FieldSource, FieldStatus, FormUpdate, UpdatesRead
from app.schemas.imports import ImportCategory, ImportItem, ImportKind, ImportList
from app.schemas.resume import FieldWrite
from app.services import activities as activity_service
from app.services import resume as resume_service
from app.services.accounts import AccountContext

NOTE_CAREER = "고용24 ‘이력보기’를 흉내 낸 모의 목록이에요. 넣을 것만 골라 주세요."
NOTE_JOB_APPLICATIONS = "고용24 ‘구직활동 불러오기’를 흉내 낸 모의 목록이에요."
NOT_FOUND_MESSAGE = "불러오기 목록에 없는 항목이에요."
RECORDED_MESSAGE = "이미 넣은 항목이에요."
TRAINING_MESSAGE = "직업훈련 이력은 대화로 알려 주세요."
JOB_APPLICATION_KIND = "job_application"
# 불러온 이력서 항목 ID 앞머리 (대화로 넣은 항목과 겹치지 않게)
ITEM_PREFIX = "imp_"


def _item(row: Work24Import) -> ImportItem:
    values: dict = {"category": row.category, "title": row.title, "detail": row.detail}
    if row.item_date is not None:
        values["date"] = row.item_date
    return ImportItem(import_id=row.source_id, is_recorded=row.is_recorded, values=values)


def _list(db: Session, account: AccountContext, kind: ImportKind, note: str) -> ImportList:
    items = [_item(row) for row in import_repo.list_kind(db, account.user_id, kind)]
    return ImportList(items=items, total=len(items), source_note=note)


def list_career_certificates(db: Session, account: AccountContext) -> ImportList:
    return _list(db, account, ImportKind.CAREER_CERTIFICATE, NOTE_CAREER)


def list_job_applications(db: Session, account: AccountContext) -> ImportList:
    return _list(db, account, ImportKind.JOB_APPLICATION, NOTE_JOB_APPLICATIONS)


def apply_imports(
    db: Session, account: AccountContext, import_ids: list[str], today: date
) -> UpdatesRead:
    """고른 항목을 넣고 바뀐 칸을 돌려줍니다. 대화의 import_ids도 같은 함수를 씁니다.

    목록에 없으면 404, 이미 넣었으면 409 CONFLICT, 직업훈련은 아직 대화로만 받아 422입니다.
    """
    rows = import_repo.get_many(db, account.user_id, list(dict.fromkeys(import_ids)))
    found = {row.source_id: row for row in rows}
    if any(i not in found for i in import_ids):
        raise NotFoundError(message=NOT_FOUND_MESSAGE)
    updates: list[FormUpdate] = []
    resume_writes: list[FieldWrite] = []
    picker = ItemPicker(resume_service.current_data(db, account.user_id))
    for row in (found[i] for i in dict.fromkeys(import_ids)):
        if row.is_recorded:
            raise ConflictError(message=RECORDED_MESSAGE)
        if row.category == ImportCategory.TRAINING:
            raise UnprocessableError(TRAINING_MESSAGE)
        if row.kind == ImportKind.JOB_APPLICATION:
            updates += _apply_application(db, account, row, today)
        else:
            resume_writes += _resume_writes(row, picker)
        row.is_recorded = True
    if resume_writes:
        updates += resume_service.save_resume_fields(
            db, account.user_id, resume_writes, today=today
        ).updates
    db.commit()
    return UpdatesRead(updates=updates)


def _apply_application(
    db: Session, account: AccountContext, row: Work24Import, today: date
) -> list[FormUpdate]:
    values = import_rules.application_values(row.title, row.detail)
    body = ActivityCreate(
        activity_date=row.item_date or today,
        kind=JOB_APPLICATION_KIND,
        route=ActivityRoute.WORK24,
        org_name=values.org_name,
        job_title=values.job_title,
    )
    result = activity_service.record_activity(
        db, account, body, today, source=FieldSource.WORK24_IMPORT, result=values.result
    )
    return result.updates


def _resume_writes(row: Work24Import, picker: ItemPicker) -> list[FieldWrite]:
    if row.category == ImportCategory.CAREER:
        v = import_rules.career_values(row.title, row.detail)
        section, name = import_rules.RESUME_SECTIONS[ImportCategory.CAREER], v.company_name
        fields = {
            "company_name": v.company_name,
            "start_date": v.start_date,
            "end_date": v.end_date,
        }
    else:
        lic = import_rules.license_values(row.title, row.detail)
        section, name = import_rules.RESUME_SECTIONS[ImportCategory.LICENSE], lic.certificate_name
        fields = {
            "certificate_name": lic.certificate_name,
            "issuing_organization": lic.issuing_organization,
            "acquired_date": lic.acquired_date,
        }
    item = picker.pick(section, values=(name,), new_id=f"{ITEM_PREFIX}{row.source_id}").item_id
    base = f"/{section}/{item}"
    return [
        FieldWrite(
            path=f"{base}/{name}",
            value=value,
            status=FieldStatus.CONFIRMED,
            source=FieldSource.WORK24_IMPORT,
        )
        for name, value in fields.items()
        if value is not None
    ]
