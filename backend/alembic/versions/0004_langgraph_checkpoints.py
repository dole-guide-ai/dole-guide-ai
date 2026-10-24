"""LangGraph 체크포인트 테이블

langgraph-checkpoint-postgres의 `setup()`이 만드는 테이블을 Alembic으로 만듭니다.
인덱스를 CONCURRENTLY로 만들어 트랜잭션 밖(autocommit)에서 실행합니다.
패키지를 올려 체크포인트 마이그레이션이 늘면 같은 방식으로 리비전을 하나 더 만듭니다.
(`setup()`은 아직 안 한 것만 실행합니다.)

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-24 12:00:00.000000

"""

from collections.abc import Sequence

from langgraph.checkpoint.postgres import PostgresSaver

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints", "checkpoint_migrations")


def upgrade() -> None:
    with op.get_context().autocommit_block():
        PostgresSaver(op.get_bind().connection.driver_connection).setup()


def downgrade() -> None:
    for table in _TABLES:
        op.execute(f"DROP TABLE IF EXISTS {table}")
