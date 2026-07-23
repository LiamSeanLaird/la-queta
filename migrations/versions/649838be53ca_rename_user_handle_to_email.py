"""rename user handle to email

Revision ID: 649838be53ca
Revises: 717126f70ce1
Create Date: 2026-07-23 15:55:58.226136

"""

from alembic import op
import sqlalchemy as sa


revision = "649838be53ca"
down_revision = "717126f70ce1"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "handle",
            new_column_name="email",
            existing_type=sa.String(length=64),
            type_=sa.String(length=254),
            existing_nullable=False,
        )
    # Normalize for case-insensitive uniqueness going forward.
    op.execute(sa.text("UPDATE users SET email = lower(email)"))


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email",
            new_column_name="handle",
            existing_type=sa.String(length=254),
            type_=sa.String(length=64),
            existing_nullable=False,
        )
