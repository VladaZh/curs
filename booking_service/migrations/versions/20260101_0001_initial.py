from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")

    op.create_table(
        "tables_replica",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("restaurant_id", sa.Uuid(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_tables_replica_restaurant_id", "tables_replica", ["restaurant_id"]
    )

    op.create_table(
        "bookings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("restaurant_id", sa.Uuid(), nullable=False),
        sa.Column("table_id", sa.Uuid(), nullable=False),
        sa.Column("guest_id", sa.Uuid(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("period", postgresql.TSTZRANGE(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("guest_id", "idempotency_key", name="uq_guest_idempotency"),
        sa.CheckConstraint("party_size > 0", name="ck_party_size_positive"),
    )
    op.create_index("ix_bookings_restaurant_id", "bookings", ["restaurant_id"])
    op.create_index("ix_bookings_guest_id", "bookings", ["guest_id"])
    # Быстрый поиск просроченных холдов для фоновой задачи
    op.create_index(
        "ix_bookings_pending_expires",
        "bookings",
        ["expires_at"],
        postgresql_where=sa.text("status = 'PENDING'"),
    )

    # Главная гарантия целостности. Alembic не умеет автогенерировать EXCLUDE, поэтому SQL вручную.
    op.execute("""
        ALTER TABLE bookings
        ADD CONSTRAINT no_overlapping_bookings
        EXCLUDE USING gist (table_id WITH =, period WITH &&)
        WHERE (status IN ('PENDING', 'CONFIRMED', 'SEATED'))
    """)

    op.create_table(
        "outbox",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("topic", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_unpublished", table_name="outbox")
    op.drop_table("outbox")
    op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS no_overlapping_bookings")
    op.drop_index("ix_bookings_pending_expires", table_name="bookings")
    op.drop_index("ix_bookings_guest_id", table_name="bookings")
    op.drop_index("ix_bookings_restaurant_id", table_name="bookings")
    op.drop_table("bookings")
    op.drop_index("ix_tables_replica_restaurant_id", table_name="tables_replica")
    op.drop_table("tables_replica")
