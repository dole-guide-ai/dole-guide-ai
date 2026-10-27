"""에이전트 도구를 그래프 없이 바로 불러 서비스와 같은 결과가 나오는지 확인합니다 (AI 설계 6.3)."""

import io
import uuid
from collections.abc import Callable
from datetime import datetime, time

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import TOOLS, TOOLS_BY_PANEL, ToolContext, ToolError, run_tool
from app.agent.tools.registry import MAX_PANEL_TOOLS
from app.core.clock import KST
from app.core.config import get_settings
from app.core.errors import ConflictError, NotFoundError
from app.schemas.files import FilePurpose
from app.services import activities as activity_service
from app.services import files as files_service
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


def test_record_activity_refuses_activity_not_counted_for_this_recipient(ctx) -> None:
    # 일반 수급자(이정호)의 자원봉사는 인정되지 않아 넣지 않고 이유를 돌려줍니다(골든셋 P-021).
    c = ctx()
    before = activity_service.list_activities(c.db, c.account, None, TEST_TODAY).items

    result = run_tool(c, "record_activity", {"when": "어제", "kind": "volunteer"})

    after = activity_service.list_activities(c.db, c.account, None, TEST_TODAY).items
    assert result["recorded"] is False
    assert result["admission"]["status"] == "not_allowed"
    assert len(after) == len(before)


def test_write_tool_refuses_private_values(ctx) -> None:
    c = ctx()

    with pytest.raises(ToolError):
        run_tool(c, "record_activity", {"when": "어제", "kind": "interview", "org_name": "[전화]"})


def test_edit_activity_corrects_then_removes_a_recorded_activity(ctx) -> None:
    # 골든셋 F-098 "그제 말고 어제였네요", F-097 회사 이름 정정, F-075 지우기
    c = ctx()
    added = run_tool(
        c, "record_activity", {"when": "그저께", "kind": "interview", "org_name": "OO유통"}
    )
    activity_id = next(u["value"]["activity_id"] for u in added["updates"] if u["op"] == "add")

    run_tool(c, "edit_activity", {"activity_id": activity_id, "when": "어제", "org_name": "OO정밀"})
    fixed = next(
        a
        for a in activity_service.list_activities(c.db, c.account, None, TEST_TODAY).items
        if str(a.activity_id) == activity_id
    )
    run_tool(c, "edit_activity", {"activity_id": activity_id, "remove": True})
    left = activity_service.list_activities(c.db, c.account, None, TEST_TODAY).items

    assert (fixed.activity_date.isoformat(), fixed.org_name) == ("2026-10-20", "OO정밀")
    assert all(str(a.activity_id) != activity_id for a in left)


def test_record_activity_marks_planned_future_activity(ctx) -> None:
    c = ctx()

    result = run_tool(
        c,
        "record_activity",
        {"when": "내일", "done": False, "kind": "interview", "org_name": "OO물류"},
    )

    assert (result["recorded"], result["planned"]) == (True, True)


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


def test_uploaded_evidence_is_attached_to_existing_activity(
    ctx, db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 시드의 OO상사(홈페이지 지원) 캡처를 올리면 새로 기록하지 않고 그 활동에 붙어야 함
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    c = ctx()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    photo = files_service.upload(
        db_session, c.account, "지원완료.png", io.BytesIO(png), FilePurpose.EVIDENCE, None
    )
    c.evidence_file_ids = files_service.evidence_ids(db_session, c.account, [photo.file_id])
    before = activity_service.list_activities(db_session, c.account, None, TEST_TODAY).items
    trading = next(a for a in before if a.org_name == "OO상사")

    result = run_tool(c, "attach_evidence", {"activity_id": trading.activity_id})

    check = next(u["value"] for u in result["updates"] if u["path"] == "/round_check")
    row = next(a for a in check["activities"] if a["activity_id"] == trading.activity_id)
    assert row["has_evidence"] is True
    after = activity_service.list_activities(db_session, c.account, None, TEST_TODAY).items
    assert len(after) == len(before)
    assert c.evidence_file_ids == []
    with pytest.raises(ToolError):  # 한 번 붙인 증빙은 다시 내주지 않음
        run_tool(c, "attach_evidence", {"activity_id": trading.activity_id})


def test_attach_evidence_to_unknown_activity_keeps_evidence(
    ctx, db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    c = ctx()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    photo = files_service.upload(
        db_session, c.account, "지원완료.png", io.BytesIO(png), FilePurpose.EVIDENCE, None
    )
    c.evidence_file_ids = [photo.file_id]

    with pytest.raises(NotFoundError):
        run_tool(c, "attach_evidence", {"activity_id": str(uuid.uuid4())})

    assert c.evidence_file_ids == [photo.file_id]


def test_evidence_stays_when_recording_fails(
    ctx, db_session: Session, tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    c = ctx()
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    photo = files_service.upload(
        db_session, c.account, "지원완료.png", io.BytesIO(png), FilePurpose.EVIDENCE, None
    )
    c.evidence_file_ids = files_service.evidence_ids(db_session, c.account, [photo.file_id])

    def fail(*args, **kwargs):
        raise ConflictError()

    monkeypatch.setattr(activity_service, "record_answered_activity", fail)
    with pytest.raises(ConflictError):
        run_tool(c, "record_activity", {"when": "오늘", "kind": "job_application"})

    assert c.evidence_file_ids == [photo.file_id]


def test_bad_tool_or_input(ctx) -> None:
    with pytest.raises(ToolError):
        run_tool(ctx(), "delete_everything", {})
    with pytest.raises(ValidationError):
        run_tool(ctx(), "record_activity", {"kind": "job_application"})


def test_allowed_path_stops_at_field_boundary(ctx) -> None:
    c = ctx("park", allowed=("/careers/c1",))

    c.ensure_allowed("/careers/c1/company_name")
    with pytest.raises(ToolError):
        c.ensure_allowed("/careers/c10/company_name")


def test_complete_education_marks_done_only_in_education_stage(ctx, db_session: Session) -> None:
    # 골든셋 P-196: 화면이 "대화창에서 '교육 다 들었어요'를 눌러 알려 주세요"라고 안내하는 경로
    from app.repositories import accounts as account_repo
    from app.schemas.procedure import Stage

    c = ctx("park")
    with pytest.raises(ConflictError):  # 구직등록 단계에서는 이수 표시를 막습니다(순서)
        run_tool(c, "complete_education", {})
    procedure = account_repo.get_procedure(db_session, c.account.user_id)
    procedure.stage = Stage.EDUCATION
    db_session.flush()

    run_tool(c, "complete_education", {})

    procedure = account_repo.get_procedure(db_session, c.account.user_id)
    assert (procedure.education_done, procedure.stage) == (True, Stage.ELIGIBILITY_APPLICATION)
