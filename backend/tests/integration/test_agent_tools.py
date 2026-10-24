"""에이전트 도구를 그래프 없이 바로 불러 서비스와 같은 결과가 나오는지 확인합니다 (AI 설계 6.3)."""

from collections.abc import Callable
from datetime import datetime, time

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.tools import TOOLS, TOOLS_BY_PANEL, ToolContext, ToolError, run_tool
from app.core.clock import KST
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
        assert 3 <= len(names) <= 4
        assert all(name in TOOLS for name in names)


def test_check_round_and_record_activity(ctx) -> None:
    c = ctx()
    before = run_tool(c, "check_round", {})
    added = run_tool(
        c,
        "record_activity",
        {
            "activity_date": TEST_TODAY.isoformat(),
            "kind": "job_application",
            "route": "work24",
            "org_name": "OO물산",
        },
    )

    after = next(u["value"] for u in added["updates"] if u["path"] == "/round_check")
    assert (before["check_status"], after["check_status"]) == ("short", "satisfied")


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


def test_overview_needs_no_llm(ctx) -> None:
    assert "네 단계" in run_tool(ctx(), "answer_overview", {})["text"]
