"""실제 모델로 대화 몇 턴을 돌려 보는 개발용 스크립트. 테스트 DB(dole_test)에만 씁니다.

    cd backend && uv run python -m scripts.dev.chat_turns "이력서 쓸게요" "말로 할게요"

- 평가 계정(eval_dev_chat)을 테스트 DB에 만들고, 끝나면 지웁니다. 개발 DB의 /personas가 빈 계정으로
  깨지는 일(2026-10-26)을 막습니다.
- 화면에 보이는 token·ask_user·form_update와 함께 error 이벤트와 원래 예외를 그대로 보여 줍니다.
  "지금 답을 만들기 어려워요"만 보일 때 원인을 찾는 용도입니다.
"""

import logging
import os
import sys
import traceback

TEST_DB = "postgresql+psycopg://dole:dole@localhost:5432/dole_test"
CASE_ID = "dev_chat"


def main(texts: list[str]) -> None:
    os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", TEST_DB)
    os.environ.setdefault("LANGSMITH_TRACING", "false")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s %(message)s")
    logging.getLogger("app.services.chat").setLevel(logging.DEBUG)  # 턴 실패의 traceback을 보여 줌

    from app.core.db import SessionLocal  # noqa: PLC0415 - DATABASE_URL을 정한 뒤에 읽어야 함
    from app.repositories import accounts as repo  # noqa: PLC0415
    from app.schemas.messages import MessageCreate  # noqa: PLC0415
    from app.services import chat as chat_service  # noqa: PLC0415
    from evals.golden.runner import TEST_DB_SUFFIX  # noqa: PLC0415
    from evals.interview.driver import AgentDriver  # noqa: PLC0415

    db = SessionLocal()
    # 지우기 전에 테스트 DB인지 먼저 봅니다(TEST_DATABASE_URL이 다른 DB를 가리켜도 건드리지 않게).
    if not str(db.get_bind().engine.url.database or "").endswith(TEST_DB_SUFFIX):
        db.close()
        sys.exit("이 스크립트는 _test로 끝나는 DB에서만 돌릴 수 있어요(TEST_DATABASE_URL).")
    try:
        _cleanup(db, repo)
        agent = AgentDriver(db, CASE_ID)
        for text in texts:
            print(f"\n>> {text}")
            turn = chat_service.start_turn(
                db, agent.account, MessageCreate(text=text), None, agent.now
            )
            try:
                for event in turn.events():
                    _show(event)
            except Exception:  # noqa: BLE001 - 원인을 보려는 스크립트
                traceback.print_exc()
            turn.finish()
    finally:
        _cleanup(db, repo)
        db.close()


def _show(event) -> None:  # noqa: ANN001
    data = event.data
    if event.name == "token":
        print("  ", repr(data.text))
    elif event.name == "ask_user":
        print(f"  [카드] {data.text} {data.choices}")
    elif event.name == "form_update":
        print(f"  [저장] {data.path} = {data.value!r}")
    elif event.name == "error":
        print(f"  [오류] {data.code}: {data.message}")


def _cleanup(db, repo) -> None:  # noqa: ANN001
    """이 스크립트가 만든 평가 계정과 persona 행을 지웁니다(users는 persona_id로 찾아 cascade)."""
    from sqlalchemy import delete, select  # noqa: PLC0415

    persona_id = f"eval_interview_{CASE_ID}"
    for user in db.scalars(select(repo.User).where(repo.User.persona_id == persona_id)):
        repo.delete_user(db, user)
    db.execute(delete(repo.Persona).where(repo.Persona.persona_id == persona_id))
    db.commit()


if __name__ == "__main__":
    main(sys.argv[1:] or ["이력서 쓸게요"])
