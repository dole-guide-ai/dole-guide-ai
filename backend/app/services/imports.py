"""고용24 불러오기(모의) 목록을 만드는 서비스입니다.

목록은 시연 계정 seed의 imports 값이고, 실제 고용24에는 연결하지 않습니다.
이미 넣었는지(is_recorded)는 지금 계정 데이터로 다시 판단합니다: 경력은 이력서 경력의 회사명,
자격은 이력서 자격의 자격증명, 입사지원은 고용24 경로로 기록된 활동의 회사명과 같으면 넣은 것으로
봅니다. 이력서에 칸이 없는 항목(직업훈련 등)은 seed 표시를 그대로 씁니다.
"""

from datetime import date
from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.repositories import accounts as repo
from app.repositories import activities as activity_repo
from app.rules import imports as import_rules
from app.schemas.common import ErrorCode
from app.schemas.imports import ImportItem, ImportList
from app.services.accounts import AccountContext
from app.services.seed import at

NOTE_CAREER = "고용24 ‘이력보기’를 흉내 낸 모의 목록이에요. 넣을 것만 골라 주세요."
NOTE_JOB_APPLICATIONS = "고용24 ‘구직활동 불러오기’를 흉내 낸 모의 목록이에요."


def list_career_certificates(db: Session, account: AccountContext) -> ImportList:
    resume = repo.get_resume(db, account.user_id)
    data = resume.data if resume else {}
    recorded = {
        "career": _names(data.get("careers", []), "company_name"),
        "license": _names(data.get("certifications", []), "certificate_name"),
    }
    items = [
        _item(raw, account.anchor_date, recorded.get(raw["category"]))
        for raw in _seed_imports(db, account.persona_id)["career_certificates"]
    ]
    return ImportList(items=items, total=len(items), source_note=NOTE_CAREER)


def list_job_applications(db: Session, account: AccountContext) -> ImportList:
    recorded = activity_repo.list_done_org_names(db, account.user_id, "work24")
    items = [
        _item(raw, account.anchor_date, recorded, name=_company(raw["title"]))
        for raw in _seed_imports(db, account.persona_id)["job_applications"]
    ]
    return ImportList(items=items, total=len(items), source_note=NOTE_JOB_APPLICATIONS)


def _seed_imports(db: Session, persona_id: str) -> dict[str, list[dict[str, Any]]]:
    persona = repo.get_persona(db, persona_id)
    if persona is None:
        raise NotFoundError(code=ErrorCode.PERSONA_NOT_FOUND)
    imports = persona.seed.get("imports") or {}
    return {
        "career_certificates": imports.get("career_certificates", []),
        "job_applications": imports.get("job_applications", []),
    }


def _item(
    raw: dict[str, Any], anchor: date, recorded: set[str] | None, name: str | None = None
) -> ImportItem:
    """seed 항목 하나를 응답 항목으로. recorded가 None이면 seed의 is_recorded를 씁니다."""
    is_recorded = import_rules.is_recorded(raw, recorded, name)
    values: dict[str, Any] = {
        "category": raw["category"],
        "title": raw["title"],
        "detail": raw["detail"],
    }
    if "date_offset" in raw:
        values["date"] = at(anchor, raw["date_offset"])
    return ImportItem(import_id=raw["import_id"], is_recorded=is_recorded, values=values)


def _names(rows: list[dict[str, Any]], key: str) -> set[str]:
    """이력서 반복 항목에서 이름 칸만 모읍니다. 칸이 FormField({value: ...})여도 값만 꺼냅니다."""
    names = set()
    for row in rows:
        value = row.get(key)
        if isinstance(value, dict):
            value = value.get("value")
        if isinstance(value, str) and value:
            names.add(value)
    return names


def _company(title: str) -> str:
    """입사지원 제목 'OO물산 · 사무보조'에서 회사명만."""
    return title.split(" · ", 1)[0]
