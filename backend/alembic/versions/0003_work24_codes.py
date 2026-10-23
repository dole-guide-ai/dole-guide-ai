"""고용24 공통코드(지역·직종) 테이블

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23 12:00:00

work24_api 스키마는 autogenerate가 보지 않으므로 손으로 씁니다 (데이터 설계 10.5 DDL).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA = "work24_api"


def upgrade() -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    op.create_table(
        "cmcdRegion",
        sa.Column("regionCd", sa.Text(), primary_key=True),
        sa.Column("regionNm", sa.Text(), nullable=False),
        sa.Column("superCd", sa.Text(), sa.ForeignKey(f"{SCHEMA}.cmcdRegion.regionCd")),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            '(depth = 1 AND "superCd" IS NULL) OR (depth = 2 AND "superCd" IS NOT NULL)',
            name="ck_cmcd_region_depth",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_cmcd_region_name", "cmcdRegion", ["regionNm"], schema=SCHEMA)
    op.create_index("idx_cmcd_region_super", "cmcdRegion", ["superCd"], schema=SCHEMA)

    op.create_table(
        "cmcdJobs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("jobsCd", sa.Text(), nullable=False),
        sa.Column("jobsNm", sa.Text(), nullable=False),
        sa.Column("superCd", sa.Text()),
        sa.Column("parent_id", sa.BigInteger(), sa.ForeignKey(f"{SCHEMA}.cmcdJobs.id")),
        sa.Column("depth", sa.SmallInteger(), nullable=False),
        sa.Column("code_path", postgresql.ARRAY(sa.Text()), nullable=False, unique=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("depth BETWEEN 1 AND 3", name="ck_cmcd_jobs_depth"),
        sa.CheckConstraint("cardinality(code_path) = depth", name="ck_cmcd_jobs_path_len"),
        sa.CheckConstraint('code_path[depth] = "jobsCd"', name="ck_cmcd_jobs_path_end"),
        sa.CheckConstraint(
            '(depth = 1 AND parent_id IS NULL AND "superCd" IS NULL)'
            ' OR (depth > 1 AND parent_id IS NOT NULL AND "superCd" IS NOT NULL)',
            name="ck_cmcd_jobs_parent",
        ),
        schema=SCHEMA,
    )
    op.create_index("idx_cmcd_jobs_code", "cmcdJobs", ["jobsCd"], schema=SCHEMA)
    op.create_index("idx_cmcd_jobs_name", "cmcdJobs", ["jobsNm"], schema=SCHEMA)
    op.create_index("idx_cmcd_jobs_super", "cmcdJobs", ["superCd"], schema=SCHEMA)
    op.create_index("idx_cmcd_jobs_parent", "cmcdJobs", ["parent_id"], schema=SCHEMA)


def downgrade() -> None:
    op.drop_table("cmcdJobs", schema=SCHEMA)
    op.drop_table("cmcdRegion", schema=SCHEMA)
    op.execute(f"DROP SCHEMA IF EXISTS {SCHEMA}")
