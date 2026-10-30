from app.models.workspace import WorkspaceOwned
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, String
from app.database import Base


class SubscriptionReceipt(WorkspaceOwned, Base):
    __tablename__ = "subscription_receipts"

    # One durable receipt per subscription, even if verification is retried.
    id = Column(String(36), ForeignKey("subscriptions.id", ondelete="CASCADE"), primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    buyer_name = Column(String(255), nullable=False)
    buyer_email = Column(String(255), nullable=False)
    plan_name = Column(String(50), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False)
    paypal_order_id = Column(String(100), nullable=False)
    paypal_capture_id = Column(String(100), nullable=False)
    is_sandbox = Column(Boolean, nullable=False)
    paid_at = Column(DateTime, nullable=False)
    expires_at = Column(DateTime, nullable=True)
    issued_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
