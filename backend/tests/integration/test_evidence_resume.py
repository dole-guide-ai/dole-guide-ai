"""질문(ask_user)에서 멈췄다 글로 답해 재개해도 앞서 올린 증빙이 활동에 붙는지 (#268).

재개 요청에는 첨부가 없으므로, 멈추기 전에 남긴 pending_evidence를 도구 문맥으로 되살려야 합니다.
"""

import io
from collections.abc import Callable

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from app.agent.responder import TurnInput, graph_responder
from app.core.config import get_settings
from app.schemas.files import FilePurpose
from app.services import activities as activity_service
from app.services import files as files_service
from app.services.accounts import AccountContext
from conftest import TEST_NOW, TEST_TODAY

pytestmark = pytest.mark.integration

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": call_id}])


@pytest.fixture(autouse=True)
def no_image_reading(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # 가짜 모델의 답을 사진 받아쓰기가 먼저 가져가지 않게 사진 읽기를 끕니다.
    monkeypatch.setattr(get_settings(), "upload_dir", str(tmp_path))
    monkeypatch.setattr(get_settings(), "image_mode", "off")


def _turn(account: AccountContext, db: Session, text: str, file_ids: list[str]) -> TurnInput:
    return TurnInput(
        account.user_id,
        account.persona_id,
        text,
        "text",
        TEST_NOW,
        file_ids=file_ids,
        db=db,
        anchor_date=account.anchor_date,
    )


def _files_of(db: Session, account: AccountContext, org_name: str) -> list[str]:
    items = activity_service.list_activities(db, account, None, TEST_TODAY).items
    return next(a.file_ids for a in items if a.org_name == org_name)


def test_evidence_survives_question_and_is_attached_after_answer(
    db_session: Session,
    entered_account: Callable[[str], AccountContext],
    fake_agent_llm,
) -> None:
    account = entered_account("lee")
    photo = files_service.upload(
        db_session, account, "지원완료.png", io.BytesIO(PNG), FilePurpose.EVIDENCE, None
    )
    items = activity_service.list_activities(db_session, account, None, TEST_TODAY).items
    trading = next(a for a in items if a.org_name == "OO상사")
    ask = _call("ask_user", {"question": "언제 지원하셨어요?", "choices": []}, "c1")
    attach = _call("attach_evidence", {"activity_id": trading.activity_id}, "c2")
    fake_agent_llm([ask, attach, AIMessage("증빙을 붙였어요.")], route="round")
    saver = InMemorySaver()

    list(graph_responder(_turn(account, db_session, "", [photo.file_id]), saver))
    assert _files_of(db_session, account, "OO상사") == []

    list(graph_responder(_turn(account, db_session, "OO상사 지원한 날이요", []), saver))

    assert _files_of(db_session, account, "OO상사") == [photo.file_id]


def test_answer_with_new_evidence_keeps_earlier_one(
    db_session: Session,
    entered_account: Callable[[str], AccountContext],
    fake_agent_llm,
) -> None:
    account = entered_account("lee")

    def upload(name: str) -> str:
        png = PNG + name.encode()  # 내용이 달라야 서로 다른 파일
        return files_service.upload(
            db_session, account, name, io.BytesIO(png), FilePurpose.EVIDENCE, None
        ).file_id

    notice, done = upload("공고.png"), upload("완료.png")
    items = activity_service.list_activities(db_session, account, None, TEST_TODAY).items
    trading = next(a for a in items if a.org_name == "OO상사")
    ask = _call("ask_user", {"question": "지원 완료 화면도 있으세요?", "choices": []}, "c1")
    attach = _call("attach_evidence", {"activity_id": trading.activity_id}, "c2")
    fake_agent_llm([ask, attach, AIMessage("둘 다 붙였어요.")], route="round")
    saver = InMemorySaver()

    list(graph_responder(_turn(account, db_session, "", [notice]), saver))
    list(graph_responder(_turn(account, db_session, "여기요", [done]), saver))

    assert sorted(_files_of(db_session, account, "OO상사")) == sorted([notice, done])


def test_new_turn_does_not_reuse_earlier_evidence(
    db_session: Session,
    entered_account: Callable[[str], AccountContext],
    fake_agent_llm,
) -> None:
    account = entered_account("lee")
    photo = files_service.upload(
        db_session, account, "지원완료.png", io.BytesIO(PNG), FilePurpose.EVIDENCE, None
    )
    items = activity_service.list_activities(db_session, account, None, TEST_TODAY).items
    trading = next(a for a in items if a.org_name == "OO상사")
    attach = _call("attach_evidence", {"activity_id": trading.activity_id}, "c1")
    fake_agent_llm([AIMessage("사진 받았어요."), attach, AIMessage("없어요.")], route="round")
    saver = InMemorySaver()

    list(graph_responder(_turn(account, db_session, "", [photo.file_id]), saver))
    # 질문 없이 끝난 턴의 증빙은 다음 새 말로 넘어가지 않습니다.
    list(graph_responder(_turn(account, db_session, "아까 거 붙여 주세요", []), saver))

    assert _files_of(db_session, account, "OO상사") == []
