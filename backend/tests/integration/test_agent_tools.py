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


def test_activity_not_done_yet_is_planned_even_today(ctx) -> None:
    # "오늘 면접 볼 거예요"는 오늘 날짜여도 예정이라 인정 건수에 들지 않습니다(CodeRabbit #280).
    added = run_tool(
        ctx(),
        "record_activity",
        {"when": "오늘", "done": False, "kind": "job_application", "org_name": "OO물산"},
    )

    values = {u["path"]: u["value"] for u in added["updates"]}
    activity = next(v for p, v in values.items() if p != "/round_check")
    assert activity["planned"] is True
    assert values["/round_check"]["check_status"] == "short"


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
