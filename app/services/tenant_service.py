from typing import List, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.core.exceptions import ConflictException, NotFoundException


class TenantService:
    @staticmethod
    def get_all(db: Session, active_only: bool = False) -> List[Tenant]:
        query = db.query(Tenant)
        if active_only:
            query = query.filter(Tenant.is_active.is_(True))
        tenants = query.order_by(Tenant.created_at.desc()).all()

        # Augment with users count
        for t in tenants:
            t.users_count = db.query(User).filter(User.tenant_id == t.id).count()
        return tenants

    @staticmethod
    def get_by_id(db: Session, tenant_id: str) -> Tenant:
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if not tenant:
            raise NotFoundException("Organización / Tenant no encontrado")
        tenant.users_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        return tenant

    @staticmethod
    def create(db: Session, data: TenantCreate) -> Tenant:
        # Check name uniqueness (máx 250 car ya validado en schema)
        clean_name = data.name.strip()
        existing_name = db.query(Tenant).filter(func.lower(Tenant.name) == clean_name.lower()).first()
        if existing_name:
            raise ConflictException(f"Ya existe una organización con el nombre '{clean_name}'. No se puede repetir el mismo nombre.")

        # Check code uniqueness
        clean_code = data.code.strip().upper()
        existing = db.query(Tenant).filter(Tenant.code == clean_code).first()
        if existing:
            raise ConflictException(f"Ya existe un tenant con el código '{clean_code}'")

        tenant = Tenant(
            name=clean_name,
            code=clean_code,
            phone=data.phone.strip() if data.phone else None,
            email=data.email.strip() if data.email else None,
            address=data.address.strip() if data.address else None,
            logo_url=data.logo_url.strip() if data.logo_url else None,
            description=data.description.strip() if data.description else None,
            is_active=data.is_active,
        )
        db.add(tenant)
        db.commit()
        db.refresh(tenant)
        tenant.users_count = 0
        return tenant

    @staticmethod
    def update(db: Session, tenant_id: str, data: TenantUpdate) -> Tenant:
        tenant = TenantService.get_by_id(db, tenant_id)
        update_data = data.model_dump(exclude_unset=True)

        if "name" in update_data and update_data["name"]:
            clean_name = update_data["name"].strip()
            existing_name = db.query(Tenant).filter(
                func.lower(Tenant.name) == clean_name.lower(),
                Tenant.id != tenant_id,
            ).first()
            if existing_name:
                raise ConflictException(f"Ya existe otra organización con el nombre '{clean_name}'. No se puede repetir el mismo nombre.")
            update_data["name"] = clean_name

        for key, value in update_data.items():
            setattr(tenant, key, value)
        db.commit()
        db.refresh(tenant)
        tenant.users_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        return tenant

    @staticmethod
    def toggle_status(db: Session, tenant_id: str) -> Tenant:
        tenant = TenantService.get_by_id(db, tenant_id)
        tenant.is_active = not tenant.is_active
        db.commit()
        db.refresh(tenant)
        tenant.users_count = db.query(User).filter(User.tenant_id == tenant.id).count()
        return tenant

    @staticmethod
    def delete(db: Session, tenant_id: str) -> None:
        tenant = TenantService.get_by_id(db, tenant_id)
        # Unlink users before deletion so they aren't deleted
        db.query(User).filter(User.tenant_id == tenant.id).update({"tenant_id": None})
        db.delete(tenant)
        db.commit()
