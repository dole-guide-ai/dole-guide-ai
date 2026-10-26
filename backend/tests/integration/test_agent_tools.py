"""에이전트 도구를 그래프 없이 바로 불러 서비스와 같은 결과가 나오는지 확인합니다 (AI 설계 6.3)."""

import io
from collections.abc import Callable
from datetime import datetime, time

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import TOOLS, TOOLS_BY_PANEL, ToolContext, ToolError, run_tool
from app.agent.tools.registry import MAX_PANEL_TOOLS
from app.core.clock import KST
from app.core.config import get_settings
from app.schemas.files import FilePurpose
from app.services import activities as activity_service
from app.services import files as files_service
from app.services import resume as resume_service
from app.services.accounts import AccountContext
from conftest import TEST_TODAY

pytestmark = pytest.mark.integration

NOW = datetime.combine(TEST_TODAY, time(9), KST)


@pytest.fixture
def ctx(db_session: Session, entered_account: Callable[[str], AccountContext]):
    def _ctx(persona_id: str = "lee", allowed: tuple[str, ...] | None = None) -> ToolContext:
        return ToolContext(db_session, entered_account(persona_id), TEST_TODAY, NOW, allowed)

    return _ctx


def test_every_panel_tool_exists_and_is_limited() -> None:
    for names in TOOLS_BY_PANEL.values():
        assert 1 <= len(names) <= MAX_PANEL_TOOLS
        assert all(name in TOOLS for name in names)


def test_check_round_and_record_activity(ctx) -> None:
    c = ctx()
    before = run_tool(c, "check_round", {})
    added = run_tool(
        c,
        "record_activity",
        {
            "when": "오늘",
            "kind": "job_application",
            "route": "work24",
            "org_name": "OO물산",
        },
    )

    after = next(u["value"] for u in added["updates"] if u["path"] == "/round_check")
    assert (before["check_status"], after["check_status"]) == ("short", "satisfied")


def test_uploaded_evidence_is_attached_to_first_recorded_activity(
    ctx, db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 대화로 올린 지원 완료 사진이 기록한 활동의 증빙으로 붙어야 함 (#246)
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    c = ctx()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    photo = files_service.upload(
        db_session, c.account, "지원완료.png", io.BytesIO(png), FilePurpose.EVIDENCE, None
    )
    c.evidence_file_ids = files_service.evidence_ids(db_session, c.account, [photo.file_id])
    first = {"when": "오늘", "kind": "job_application", "route": "work24", "org_name": "OO물산"}

    run_tool(c, "record_activity", first)
    run_tool(c, "record_activity", first | {"when": "어제", "org_name": "OO상사"})

    activities = activity_service.list_activities(db_session, c.account, None, TEST_TODAY).items
    by_org = {a.org_name: a.file_ids for a in activities}
    assert by_org["OO물산"] == [photo.file_id]
    assert by_org["OO상사"] == []


def test_write_tools_only_touch_allowed_paths(ctx) -> None:
    c = ctx("park", allowed=("/resume_title",))

    ok = run_tool(c, "save_resume_fields", {"fields": [{"path": "/resume_title", "value": "제목"}]})
    assert ok["updates"]
    with pytest.raises(ToolError):
        run_tool(c, "save_resume_fields", {"fields": [{"path": "/careers/c1/company_name"}]})


def test_bad_tool_or_input(ctx) -> None:
    with pytest.raises(ToolError):
        run_tool(ctx(), "delete_everything", {})
    with pytest.raises(ValidationError):
        run_tool(ctx(), "record_activity", {"kind": "job_application"})


def test_record_resume_facts_saves_with_code_decided_paths(ctx) -> None:
    """모델은 사실과 날짜 표현만 넘기고, 칸 경로·항목 id·날짜는 코드가 정합니다."""
    facts = {
        "careers": [{"company_name": "OO산업", "start": "2004년 3월", "end": "지금까지"}],
        "certifications": [{"certificate_name": "지게차운전기능사", "acquired": "2011년"}],
    }
    result = run_tool(ctx("park"), "record_resume_facts", facts)

    assert result["saved"] == 5
    paths = {u["path"] for u in result["updates"]}
    assert any(p.endswith("/start_date") for p in paths)


def test_record_resume_facts_asks_instead_of_guessing_vague_date(ctx) -> None:
    result = run_tool(ctx("park"), "record_resume_facts", {"careers": [{"start": "재작년 겨울"}]})

    assert result["saved"] == 0
    assert result["ask"]


def test_allowed_path_stops_at_field_boundary(ctx) -> None:
    c = ctx("park", allowed=("/careers/c1",))

    c.ensure_allowed("/careers/c1/company_name")
    with pytest.raises(ToolError):
        c.ensure_allowed("/careers/c10/company_name")


def test_save_resume_fields_reaches_every_resume_section(ctx) -> None:
    """대화로 이력서의 어느 칸이든 쓸 수 있습니다(record_resume_facts에 없는 칸 포함)."""
    c = ctx("park")
    run_tool(
        c,
        "record_resume_facts",
        {
            "careers": [{"company_name": "OO물류", "start": "2012년 3월", "end": "2026년 9월"}],
            "education": [{"school_name": "OO고등학교", "education_level": "고등학교"}],
            "certifications": [{"certificate_name": "지게차운전기능사"}],
        },
    )
    fields = [
        {"path": "/resume_title", "value": "물류 경력 이력서"},
        {
            "path": "/job_preferences/desired_salary",
            "value": {"amount": None, "unit": "monthly", "currency": "KRW", "negotiable": True},
        },
        {"path": "/job_preferences/employment_contract_type", "value": "관계없음"},
        {"path": "/job_preferences/military_alternative", "value": "해당 없음"},
        {
            "path": "/competencies/computer_skills",
            "value": {"selected_skills": ["엑셀"], "other_skills": None},
        },
        {"path": "/additional_info/can_drive", "value": True},
        {"path": "/careers/c1/monthly_salary", "value": 2800000},
        {"path": "/education/e1/major", "value": "기계과"},
        {"path": "/certifications/q1/issuing_organization", "value": "한국산업인력공단"},
    ]
    result = run_tool(c, "save_resume_fields", {"fields": fields})
    assert result["updates"]
    run_tool(
        c,
        "save_resume_fields",
        {"fields": [{"path": "/competencies_status", "not_applicable": True}]},
    )

    data = resume_service.read_resume(c.db, c.account).data
    assert data.resume_title.value == "물류 경력 이력서"
    assert data.job_preferences.desired_salary.value["negotiable"] is True
    assert data.job_preferences.employment_contract_type.value == "관계없음"
    assert data.competencies.computer_skills.value["selected_skills"] == ["엑셀"]
    assert data.additional_info.can_drive.value is True
    assert data.careers[0].monthly_salary.value == 2800000
    assert data.education[0].major.value == "기계과"
    assert data.certifications[0].issuing_organization.value == "한국산업인력공단"
    assert data.competencies_status.status == "not_applicable"
