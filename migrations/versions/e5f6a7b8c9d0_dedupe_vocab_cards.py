"""Merge duplicate vocab cards so each word lives in exactly one deck.

Each removed card maps to the card that now owns the word. Per user, the kept
card's `seen` becomes the highest `seen` across the copies (so retired beats
anything, and 2 views beats 1). Then the removed cards and their progress rows
are deleted.

Data-only migration. The mapping is frozen here on purpose: it must not change
when deck content changes later.

Revision ID: e5f6a7b8c9d0
Revises: c3d4e5f6a7b8
Create Date: 2026-11-16
"""

import sqlalchemy as sa
from alembic import op

revision = "e5f6a7b8c9d0"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None

# removed external_id -> kept external_id(s)
MERGES: dict[str, tuple[str, ...]] = {
    # courtesy / survival phrases -> starter
    "soc001": ("greet_010",),  # si us plau
    "soc002": ("greet_008",),  # gràcies
    "soc004": ("greet_009",),  # de res
    "soc005": ("greet_011",),  # perdona
    "soc009": ("basic_011",),  # d'acord
    "sg_009": ("basic_011",),  # d'acord
    "soc011": ("basic_003",),  # no (ho) entenc
    "soc018": ("basic_009",),  # tinc gana
    "soc019": ("basic_010",),  # tinc set
    "ev_004": ("basic_014",),  # ara
    "ev_005": ("basic_015",),  # després
    # shopping
    "basic_007": ("sh_003",),  # quant costa?
    # time -> days_months
    "ev_001": ("dm_020",),  # avui
    "ev_003": ("dm_021",),  # demà
    "ev_002": ("dm_022",),  # ahir
    "tr_012": ("dm_027",),  # a quina hora?
    # meal verbs -> home_daily
    "ev_026": ("hd024",),  # esmorzar
    "ev_027": ("hd025",),  # dinar
    "ev_028": ("hd026",),  # sopar
    # same-deck repeats
    "ev_041": ("ev_021",),  # el cafè
    "ev_044": ("ev_019",),  # el vi
    "ev_043": ("ev_020",),  # la cervesa
    "tr_052": ("tr_019",),  # el mapa
    # places -> health
    "tr_026": ("hl_001",),  # la farmàcia
    "tr_027": ("hl_002",),  # l'hospital
    # phrases -> travel
    "ad_009": ("tr_030",),  # necessito ajuda
    # open / closed / entrance
    "sg_001": ("ev_035",),  # obert
    "sg_002": ("ev_036",),  # tancat
    "sh_012": ("ev_035", "ev_036"),  # obert / tancat
    "sg_006": ("hd007",),  # entrada
}


def _card_id(conn, external_id: str) -> int | None:
    return conn.execute(
        sa.text("SELECT id FROM cards WHERE external_id = :e"), {"e": external_id}
    ).scalar()


def upgrade():
    conn = op.get_bind()
    for removed_ext, kept_exts in MERGES.items():
        removed_id = _card_id(conn, removed_ext)
        if removed_id is None:
            continue  # fresh DB, or already merged

        for kept_ext in kept_exts:
            kept_id = _card_id(conn, kept_ext)
            if kept_id is None:
                # Kept card not seeded yet: create a placeholder by cloning the
                # removed row; the next seed overwrites its fields and deck.
                conn.execute(
                    sa.text(
                        "INSERT INTO cards (deck_id, external_id, catalan, english, "
                        "pronunciation, hint, pos, gender, plural, tags_json, forms_json, "
                        "grammar_lesson_id) "
                        "SELECT deck_id, :k, catalan, english, pronunciation, hint, pos, "
                        "gender, plural, tags_json, forms_json, grammar_lesson_id "
                        "FROM cards WHERE id = :r"
                    ),
                    {"k": kept_ext, "r": removed_id},
                )
                kept_id = _card_id(conn, kept_ext)

            # Raise existing kept rows to the max seen.
            conn.execute(
                sa.text(
                    "UPDATE user_card_progress AS k SET seen = r.seen "
                    "FROM user_card_progress AS r "
                    "WHERE k.card_id = :kept AND r.card_id = :removed "
                    "AND r.user_id = k.user_id AND r.seen > k.seen"
                ),
                {"kept": kept_id, "removed": removed_id},
            )
            # Users who only studied the removed copy get a kept row.
            conn.execute(
                sa.text(
                    "INSERT INTO user_card_progress (user_id, card_id, seen) "
                    "SELECT r.user_id, :kept, r.seen FROM user_card_progress AS r "
                    "WHERE r.card_id = :removed AND NOT EXISTS ("
                    "  SELECT 1 FROM user_card_progress AS k "
                    "  WHERE k.card_id = :kept AND k.user_id = r.user_id)"
                ),
                {"kept": kept_id, "removed": removed_id},
            )

        conn.execute(
            sa.text("DELETE FROM user_card_progress WHERE card_id = :r"),
            {"r": removed_id},
        )
        conn.execute(sa.text("DELETE FROM cards WHERE id = :r"), {"r": removed_id})


def downgrade():
    # Merged progress cannot be split back apart. Restore the pre-deploy
    # SQLite backup if this ever needs undoing; re-seeding older content
    # recreates the removed cards with no progress.
    pass
