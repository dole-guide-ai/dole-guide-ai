"""LangGraph 체크포인터 (그래프 상태를 대화마다 Postgres에 저장).

`thread_id`는 계정(user_id) 하나에 대화 하나입니다(`responder.run_config`). 테이블은
Alembic 0004 마이그레이션이 만들고, 앱은 `setup()`을 부르지 않습니다.
테스트는 `InMemorySaver`를 씁니다.
"""

from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.engine import make_url

from app.core.config import get_settings

# langgraph-checkpoint-postgres가 만드는 테이블. Alembic autogenerate가 지우지 않게 뺍니다.
CHECKPOINT_TABLES = frozenset(
    {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}
)
POOL_MAX_SIZE = 5


def conninfo(database_url: str) -> str:
    """SQLAlchemy URL(`postgresql+psycopg://`)을 psycopg가 읽는 접속 문자열로 바꿉니다."""
    url = make_url(database_url).set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


@lru_cache(maxsize=1)
def get_checkpointer() -> PostgresSaver:
    pool = ConnectionPool(
        conninfo(get_settings().database_url),
        max_size=POOL_MAX_SIZE,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    return PostgresSaver(pool)
