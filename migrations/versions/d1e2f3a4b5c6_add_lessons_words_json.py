"""add lessons.words_json

The "Words in this lesson" list: every Catalan word or phrase the lesson's
test asks for, with its English. Content only; seeded from content/lessons.

Revision ID: d1e2f3a4b5c6
Revises: c9d0e1f2a3b4
Create Date: 2026-11-19 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


revision = "d1e2f3a4b5c6"
down_revision = "c9d0e1f2a3b4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "words_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.drop_column("words_json")
