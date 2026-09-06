from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(String(50), primary_key=True)  # E.g. ADMIN_SAAS, ADMIN_ORGANIZATION, NUTRICIONISTA, CLIENTE
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    platform = Column(String(100), nullable=False)  # Web, Móvil, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    users = relationship("User", back_populates="role")
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(String(50), primary_key=True)  # E.g. tenants:manage, users:manage, clinical:manage, patient:self
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    module = Column(String(50), nullable=False)  # SaaS, Organización, Clínica, Paciente

    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(String(50), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id = Column(String(50), ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="role_permissions")
