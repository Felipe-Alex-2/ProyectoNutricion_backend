import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, UniqueConstraint
from app.database import Base


class Branch(Base):
    __tablename__ = 'branches'
    __table_args__ = (UniqueConstraint('tenant_id', 'code', name='uq_branch_company_code'),)
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String(250), nullable=False)
    code = Column(String(50), nullable=False)
    address = Column(String(255), nullable=True)
    province_code = Column(String(4), nullable=True)
    municipality_code = Column(String(6), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class CompanyAdministrator(Base):
    __tablename__ = 'company_administrators'
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='CASCADE'), primary_key=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='RESTRICT'), nullable=False, unique=True)
