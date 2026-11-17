"""add cards.position

Cards were listed by primary key, so cards added to or moved into a deck after
the first seed showed at the end instead of where the deck file puts them.
position stores each card's index in its deck file; the next seed fills it in.

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-11-16 18:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "a7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("position", sa.Integer(), nullable=False, server_default="0")
        )


def downgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("position")
