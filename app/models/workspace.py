"""Ownership columns copied by SQLAlchemy into each operational model."""
from sqlalchemy import Column, ForeignKey, String


class WorkspaceOwned:
    tenant_id = Column(String(36), ForeignKey('tenants.id', ondelete='SET NULL'), nullable=True, index=True)
    branch_id = Column(String(36), ForeignKey('branches.id', ondelete='SET NULL'), nullable=True, index=True)
