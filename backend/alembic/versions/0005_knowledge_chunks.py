"""knowledge_chunks 검색 색인 테이블 (규칙 카드 + 정책·FAQ 청크, 벡터 1024차원)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26 00:46:21.841139

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "knowledge_chunks",
        sa.Column("chunk_id", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("meta", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_model", sa.String(length=80), nullable=False),
        sa.Column("embedding", Vector(dim=1024), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('rule_card', 'faq', 'policy')", name=op.f("ck_knowledge_chunks_kind")
        ),
        sa.PrimaryKeyConstraint("chunk_id", name=op.f("pk_knowledge_chunks")),
    )
    op.create_index(op.f("ix_knowledge_chunks_kind"), "knowledge_chunks", ["kind"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_knowledge_chunks_kind"), table_name="knowledge_chunks")
    op.drop_table("knowledge_chunks")
