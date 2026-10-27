from collections.abc import Callable

import pytest
from sqlalchemy.orm import Session

from app.core.errors import UnprocessableError
from app.repositories import accounts as repo
from app.schemas.resume import FieldWrite
from app.services.accounts import AccountContext
from app.services.resume import read_resume, save_resume_fields
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
    completeness = result.updates[0].completeness
    assert completeness is not None and completeness.filled == 0 and completeness.total == 5
    # 직급(꼭 채울 칸)을 하던 일(더 좋게 하는 칸)보다 먼저 묻습니다.
    assert read_resume(db_session, park).next_question == "resume.career_position"


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
    assert result.updates
    assert read_resume(db_session, choi).next_question == "resume.career_since_old"


def test_rejects_wrong_value_shape(
    db_session: Session, entered_account: Callable[[str], AccountContext]
) -> None:
    park = entered_account("park")
    for path, value in (
        ("/job_preferences/desired_occupations/o1/occupation", "시설관리"),
        ("/job_preferences/desired_regions", "서울 노원구"),
    ):
        with pytest.raises(UnprocessableError):
            save_resume_fields(
                db_session, park.user_id, [FieldWrite(path=path, value=value)], today=TEST_TODAY
            )


def test_upgrades_resume_saved_in_old_structure(
    db_session: Session, entered_account: Callable[[str], AccountContext]
) -> None:
    # #166 이전 seed로 만든 행(title, level·is_final, 값만 있는 경력)
    choi = entered_account("choi")
    resume = repo.get_resume(db_session, choi.user_id)
    resume.data = {
        "title": {"value": "시설관리 경력 이력서", "status": "extracted", "source": "seed"},
        "education": [{"item_id": "edu_001", "level": "고등학교", "is_final": True}],
        "job_preferences": {
            "desired_occupations": [
                {"code": None, "name": "시설관리", "status": "needs_confirmation"}
            ],
            "desired_regions": ["서울 노원구"],
        },
        "careers": [{"item_id": "career_001", "company_name": "OO아파트 관리사무소"}],
        "certifications": [],
        "competencies": {},
    }
    db_session.flush()

    save_resume_fields(
        db_session,
        choi.user_id,
        [FieldWrite(path="/job_preferences/military_alternative", value="해당 없음")],
        today=TEST_TODAY,
    )
    data = repo.get_resume(db_session, choi.user_id).data
    assert data["resume_title"]["value"] == "시설관리 경력 이력서"
    assert data["education"][0]["education_level"]["value"] == "고등학교"
    assert data["careers"][0]["company_name"]["source"] == "seed"
    occ = data["job_preferences"]["desired_occupations"][0]["occupation"]["value"]
    assert occ["name"] == "시설관리"
    assert data["job_preferences"]["desired_regions"]["value"] == [
        {"code": None, "name": "서울 노원구"}
    ]
