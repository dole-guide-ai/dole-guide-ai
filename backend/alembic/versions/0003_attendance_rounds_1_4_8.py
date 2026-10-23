"""출석 회차를 모든 그룹 1·4·8차로 보정

60세 이상·장애인 그룹도 8차에 출석하도록 규칙(`periods.is_attendance_round`)을 고쳤으므로,
이전 규칙으로 만든 회차 행의 `attendance_required`도 같은 규칙으로 맞춥니다 (N-12, form-011).

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-23 01:30:00

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """회차 번호로 출석 여부를 다시 정합니다."""
    op.execute("UPDATE rounds SET attendance_required = (round_no IN (1, 4, 8))")


def downgrade() -> None:
    """이전 규칙: 일반은 1·4·8차, 그 밖의 그룹은 1·4차."""
    op.execute(
        """
        UPDATE rounds AS r
        SET attendance_required = CASE
            WHEN p.recipient_group = 'general' THEN r.round_no IN (1, 4, 8)
            ELSE r.round_no IN (1, 4)
        END
        FROM procedure_states AS p
        WHERE p.user_id = r.user_id
        """
    )
