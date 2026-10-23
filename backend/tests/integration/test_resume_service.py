from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.core.errors import UnprocessableError
from app.repositories import accounts as repo
from app.schemas.resume import FieldWrite
from app.services.accounts import AccountContext
from app.services.resume import save_resume_fields
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration


def test_writes_new_career_and_derives_values(
    db_session: Session, entered_account: Callable[[str], AccountContext]
) -> None:
    park = entered_account("park")  # 이력서 없음 → draft로 만들어짐
    writes = [
        FieldWrite(path="/careers/c1/company_name", value="OO산업", source="doc"),
        FieldWrite(path="/careers/c1/start_date", value="2004-03", source="doc"),
        FieldWrite(path="/careers/c1/end_date", value="2026-09", source="doc"),
    ]
    result = save_resume_fields(db_session, park.user_id, writes, today=TEST_TODAY)

    resume = repo.get_resume(db_session, park.user_id)
    assert resume.status == "draft" and resume.lock_version == 2
    assert resume.data["careers"][0]["company_name"]["value"] == "OO산업"
    paths = {u.path for u in result.updates}
    assert "/careers/c1/company_name" in paths
    assert "/careers/c1/employment_status" in paths  # 자동 값(퇴직)도 알림
    assert result.updates[0].completeness == {"filled": 0, "total": 5}
    assert result.next_question.id == "resume.career_duties"


def test_rejects_fourth_region_and_unknown_field(
    db_session: Session, entered_account: Callable[[str], AccountContext]
) -> None:
    park = entered_account("park")
    regions = [{"code": None, "name": n} for n in ("가", "나", "다", "라")]
    with pytest.raises(UnprocessableError):
        save_resume_fields(
            db_session,
            park.user_id,
            [FieldWrite(path="/job_preferences/desired_regions", value=regions)],
            today=TEST_TODAY,
        )
    for path in ("/status", "/careers/c1/no_such_field", "/resume_title/value"):
        with pytest.raises(UnprocessableError):
            save_resume_fields(
                db_session, park.user_id, [FieldWrite(path=path, value="x")], today=TEST_TODAY
            )


def test_old_resume_from_seed_asks_since_then(
    db_session: Session, entered_account: Callable[[str], AccountContext]
) -> None:
    choi = entered_account("choi")
    result = save_resume_fields(
        db_session,
        choi.user_id,
        [FieldWrite(path="/job_preferences/military_alternative", value="해당 없음")],
        today=TEST_TODAY,
    )
    assert result.next_question.id == "resume.career_since_old"
