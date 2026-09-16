import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import relationship
from app.database import Base


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    plan_name = Column(String(50), nullable=False)  # BASICO, PROFESIONAL, PREMIUM, CLIENTE_FREE, CLIENTE_PREMIUM
    paypal_order_id = Column(String(100), nullable=True, index=True)
    paypal_capture_id = Column(String(100), nullable=True)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, ACTIVE, CANCELLED, EXPIRED
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD", nullable=False)
    started_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="subscriptions")
    user = relationship("User", backref="subscriptions")
