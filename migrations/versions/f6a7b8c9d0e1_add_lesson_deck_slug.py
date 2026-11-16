"""add lessons.deck_slug

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.add_column(sa.Column("deck_slug", sa.String(length=64), nullable=True))


def downgrade():
    with op.batch_alter_table("lessons", schema=None) as batch_op:
        batch_op.drop_column("deck_slug")
