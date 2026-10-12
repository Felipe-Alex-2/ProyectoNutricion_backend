"""Persist immutable payment receipts for subscriptions."""
from alembic import op
import sqlalchemy as sa

revision = "20261012_02"
down_revision = "20261011_01"
branch_labels = None
depends_on = None


def upgrade():
    # Allows adoption of a development database created from current metadata.
    if sa.inspect(op.get_bind()).has_table("subscription_receipts"):
        return
    op.create_table("subscription_receipts",
        sa.Column("id", sa.String(36), sa.ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("buyer_name", sa.String(255), nullable=False),
        sa.Column("buyer_email", sa.String(255), nullable=False),
        sa.Column("plan_name", sa.String(50), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("paypal_order_id", sa.String(100), nullable=False),
        sa.Column("paypal_capture_id", sa.String(100), nullable=False),
        sa.Column("is_sandbox", sa.Boolean(), nullable=False),
        sa.Column("paid_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_subscription_receipts_user_id", "subscription_receipts", ["user_id"])


def downgrade():
    raise RuntimeError("No se eliminan comprobantes de pago automáticamente.")
