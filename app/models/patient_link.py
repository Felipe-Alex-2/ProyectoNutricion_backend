import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class PatientNutritionistLink(Base):
    __tablename__ = "patient_nutritionist_links"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True)
    nutritionist_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    pairing_code = Column(String(30), unique=True, index=True, nullable=False)
    whatsapp_number = Column(String(50), default="+591 73683564", nullable=False)
    status = Column(String(20), default="PENDING", nullable=False)  # PENDING, LINKED, EXPIRED, CANCELLED
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    linked_at = Column(DateTime, nullable=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="patient_links")
    nutritionist = relationship("User", foreign_keys=[nutritionist_id])
    patient = relationship("User", foreign_keys=[patient_id])
