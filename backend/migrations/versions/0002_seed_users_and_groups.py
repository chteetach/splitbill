"""Seed the four users and two groups from the brief.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-12
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

USERS = ["alice", "bob", "carol", "dan"]
GROUPS = {1: ("Chiang Mai trip", ["alice", "bob", "carol"]), 2: ("Office lunch", ["bob", "dan"])}


def upgrade() -> None:
    conn = op.get_bind()
    for username in USERS:
        conn.execute(sa.text("INSERT INTO users (username) VALUES (:u)"), {"u": username})
    for group_id, (name, members) in GROUPS.items():
        conn.execute(
            sa.text("INSERT INTO groups (id, name) VALUES (:id, :name)"),
            {"id": group_id, "name": name},
        )
        for username in members:
            conn.execute(
                sa.text(
                    "INSERT INTO group_members (group_id, user_id) "
                    "SELECT :g, id FROM users WHERE username = :u"
                ),
                {"g": group_id, "u": username},
            )
    # Explicit ids were inserted above, so move the sequence past them.
    conn.execute(sa.text("SELECT setval('groups_id_seq', (SELECT MAX(id) FROM groups))"))


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text("DELETE FROM group_members WHERE group_id = ANY(:ids)"), {"ids": list(GROUPS)}
    )
    conn.execute(sa.text("DELETE FROM groups WHERE id = ANY(:ids)"), {"ids": list(GROUPS)})
    conn.execute(sa.text("DELETE FROM users WHERE username = ANY(:u)"), {"u": USERS})
