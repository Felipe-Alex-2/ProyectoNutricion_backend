from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.core.authorization import require_role, require_tenant
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse
from app.services.tenant_service import TenantService

router = APIRouter(prefix="/tenants", tags=["Tenants"])


@router.get("", response_model=List[TenantResponse])
def list_tenants(
    active_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role_id != "ADMIN_SAAS":
        return [TenantService.get_by_id(db, current_user.tenant_id)] if current_user.tenant_id else []
    return TenantService.get_all(db, active_only=active_only)


@router.get("/public", response_model=List[TenantResponse])
def list_public_tenants(
    db: Session = Depends(get_db),
):
    """Retorna las sucursales/clínicas activas disponibles públicamente para el registro de clientes."""
    return TenantService.get_all(db, active_only=True)


@router.get("/{tenant_id}", response_model=TenantResponse)
def get_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_tenant(current_user, tenant_id)
    return TenantService.get_by_id(db, tenant_id)


@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def create_tenant(
    data: TenantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, {"ADMIN_SAAS"})
    return TenantService.create(db, data)


@router.put("/{tenant_id}", response_model=TenantResponse)
def update_tenant(
    tenant_id: str,
    data: TenantUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, {"ADMIN_SAAS"})
    return TenantService.update(db, tenant_id, data)


@router.patch("/{tenant_id}/toggle", response_model=TenantResponse)
def toggle_tenant_status(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, {"ADMIN_SAAS"})
    return TenantService.toggle_status(db, tenant_id)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(
    tenant_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_role(current_user, {"ADMIN_SAAS"})
    TenantService.delete(db, tenant_id)
    return None
