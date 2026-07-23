"""add lessons.practice_json

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-23 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "practice_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.drop_column("practice_json")
