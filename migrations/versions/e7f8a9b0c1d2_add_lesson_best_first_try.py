"""add user_lesson_progress.best_first_try

The learner's best test score for a lesson: how many questions they answered
right on the first try. NULL means no score was recorded, which is every row
completed before scoring existed; those lessons show as completed with 1 star.
The column is added empty, so no existing progress changes.

Revision ID: e7f8a9b0c1d2
Revises: d1e2f3a4b5c6
Create Date: 2026-11-19 15:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "e7f8a9b0c1d2"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("user_lesson_progress", schema=None) as batch_op:
        batch_op.add_column(sa.Column("best_first_try", sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table("user_lesson_progress", schema=None) as batch_op:
        batch_op.drop_column("best_first_try")
