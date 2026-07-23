"""handle required + optional email (no email resume)

Revision ID: a1b2c3d4e5f6
Revises: 649838be53ca
Create Date: 2026-07-23 16:10:00.000000

"""

from __future__ import annotations

import re

import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "649838be53ca"
branch_labels = None
depends_on = None

HANDLE_RE = re.compile(r"^[a-zA-Z0-9_-]{3,24}$")
EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")


def _derive_handle(raw: str, user_id: int, used: set[str]) -> str:
    candidate = raw
    if EMAIL_RE.fullmatch(raw):
        local = raw.split("@", 1)[0]
        local = re.sub(r"[^a-zA-Z0-9_-]", "", local)[:24]
        candidate = local if HANDLE_RE.fullmatch(local) else f"user{user_id}"
    elif not HANDLE_RE.fullmatch(raw):
        candidate = f"user{user_id}"

    base = candidate
    n = 2
    while candidate.lower() in used:
        suffix = str(n)
        candidate = f"{base[: 24 - len(suffix)]}{suffix}"
        n += 1
    used.add(candidate.lower())
    return candidate


def upgrade():
    conn = op.get_bind()
    cols = {row[1] for row in conn.execute(sa.text("PRAGMA table_info(users)")).fetchall()}

    if "handle" not in cols:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(sa.Column("handle", sa.String(length=64), nullable=True))

    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    used: set[str] = set()
    for user_id, email_val in rows:
        email_val = email_val or ""
        handle = _derive_handle(email_val, user_id, used)
        conn.execute(
            sa.text("UPDATE users SET handle = :h WHERE id = :id"),
            {"h": handle, "id": user_id},
        )

    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column("handle", existing_type=sa.String(length=64), nullable=False)
        batch_op.create_unique_constraint("uq_users_handle", ["handle"])
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=254),
            nullable=True,
        )

    # Former short handles lived in email after the prior rename — clear those.
    rows = conn.execute(sa.text("SELECT id, email FROM users")).fetchall()
    for user_id, email_val in rows:
        if email_val and not EMAIL_RE.fullmatch(email_val):
            conn.execute(
                sa.text("UPDATE users SET email = NULL WHERE id = :id"),
                {"id": user_id},
            )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE users SET email = lower(handle) || '@invalid.local' "
            "WHERE email IS NULL OR email = ''"
        )
    )
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.alter_column(
            "email",
            existing_type=sa.String(length=254),
            nullable=False,
        )
        batch_op.drop_constraint("uq_users_handle", type_="unique")
        batch_op.drop_column("handle")
