from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inbox",
        sa.Column("source", sa.String(64), primary_key=True),
        sa.Column("message_id", sa.String(64), primary_key=True),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_inbox_received_at", "inbox", ["received_at"])

    op.create_table(
        "users_replica",
        sa.Column("user_id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )

    op.create_table(
        "restaurants_replica",
        sa.Column("restaurant_id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
    )

    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("booking_id", sa.Uuid(), nullable=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_data", postgresql.JSONB(), nullable=False),
        sa.Column("dedup_key", sa.String(128), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("dedup_key", name="uq_notification_dedup"),
    )
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"])
    op.create_index("ix_notifications_booking_id", "notifications", ["booking_id"])
    op.create_index("ix_notifications_due", "notifications", ["next_attempt_at"],
                    postgresql_where=sa.text("status IN ('PENDING','SENDING')"))


def downgrade() -> None:
    op.drop_index("ix_notifications_due", table_name="notifications")
    op.drop_index("ix_notifications_booking_id", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
    op.drop_table("restaurants_replica")
    op.drop_table("users_replica")
    op.drop_index("ix_inbox_received_at", table_name="inbox")
    op.drop_table("inbox")
