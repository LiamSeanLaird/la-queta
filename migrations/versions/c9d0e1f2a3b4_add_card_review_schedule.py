"""add review schedule to user_card_progress

Spaced repetition needs to know, per learner and card, how far apart reviews
are now (interval_days) and when the card is next due (due_at). Existing
progress carries over from `seen`, which so far counted views:

    seen 0   -> interval 0, due_at NULL (never studied)
    seen 1   -> interval 1, due now
    seen 2   -> interval 3, due now
    seen 3+  -> interval 7, due now (still retired: `seen` is unchanged)

Every studied card is due straight away because nobody has graded it yet, so
the first review after deploy checks what the learner really remembers.

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-11-17 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_card_progress") as batch:
        batch.add_column(
            sa.Column("interval_days", sa.Integer(), nullable=False, server_default="0")
        )
        batch.add_column(sa.Column("due_at", sa.DateTime(), nullable=True))
        batch.add_column(sa.Column("last_reviewed_at", sa.DateTime(), nullable=True))

    op.execute(
        "UPDATE user_card_progress SET "
        "interval_days = CASE WHEN seen >= 3 THEN 7 WHEN seen = 2 THEN 3 ELSE 1 END, "
        "due_at = CURRENT_TIMESTAMP "
        "WHERE seen > 0"
    )


def downgrade():
    with op.batch_alter_table("user_card_progress") as batch:
        batch.drop_column("last_reviewed_at")
        batch.drop_column("due_at")
        batch.drop_column("interval_days")
