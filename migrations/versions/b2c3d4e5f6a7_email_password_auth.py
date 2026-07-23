"""email+password auth (no email verification)

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-23 16:15:00.000000

"""

from __future__ import annotations

import secrets

import sqlalchemy as sa
from alembic import op
from werkzeug.security import generate_password_hash

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("password_hash", sa.String(length=255), nullable=True)
        )

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for user_id, email in rows:
        # Unusable random password — legacy cookie sessions still work until cleared.
        pwd_hash = generate_password_hash(secrets.token_urlsafe(32))
        if not email:
            email = f"legacy{user_id}@invalid.local"
        conn.execute(
            sa.text(
                "UPDATE users SET password_hash = :p, email = :e WHERE id = :id"
            ),
            {"p": pwd_hash, "e": email, "id": user_id},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "password_hash",
            existing_type=sa.String(length=255),
            nullable=False,
        )
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=254),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("password_hash")
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=254),
            nullable=True,
        )
