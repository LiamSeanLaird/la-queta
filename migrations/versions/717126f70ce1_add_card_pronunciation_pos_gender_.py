"""add card pronunciation pos gender plural forms

Revision ID: 717126f70ce1
Revises: 8bc38f339139
Create Date: 2026-07-23 09:05:09.765652

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "717126f70ce1"
down_revision = "8bc38f339139"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pronunciation",
                sa.String(length=200),
                nullable=False,
                server_default="",
            )
        )
        batch_op.add_column(
            sa.Column("pos", sa.String(length=32), nullable=False, server_default="")
        )
        batch_op.add_column(sa.Column("gender", sa.String(length=8), nullable=True))
        batch_op.add_column(sa.Column("plural", sa.String(length=120), nullable=True))
        batch_op.add_column(
            sa.Column(
                "forms_json",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'"),
            )
        )


def downgrade():
    with op.batch_alter_table("cards", schema=None) as batch_op:
        batch_op.drop_column("forms_json")
        batch_op.drop_column("plural")
        batch_op.drop_column("gender")
        batch_op.drop_column("pos")
        batch_op.drop_column("pronunciation")
