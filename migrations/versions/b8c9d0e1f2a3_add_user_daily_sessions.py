"""add user_daily_sessions

Nothing was stored when a learner finished daily vocab, so the app could not
show "done for today" or a streak. Each row is one finished daily session on
one local calendar day. New table only; existing progress is untouched.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-11-17 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "b8c9d0e1f2a3"
down_revision = "a7b8c9d0e1f2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_daily_sessions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("level_id", sa.String(length=16), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["level_id"], ["levels.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "local_date", name="uq_user_daily_session"),
    )


def downgrade():
    op.drop_table("user_daily_sessions")
