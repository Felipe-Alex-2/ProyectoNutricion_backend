from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.rbac import RoleResponse, PermissionResponse, UpdateRolePermissionsRequest
from app.services.rbac_service import RBACService

router = APIRouter(prefix="/roles", tags=["Roles & Permisos"])


@router.get("", response_model=List[RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RBACService.get_all_roles(db)


@router.get("/permissions", response_model=List[PermissionResponse])
def get_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RBACService.get_all_permissions(db)


@router.put("/{role_id}/permissions", response_model=RoleResponse)
def update_role_permissions(
    role_id: str,
    data: UpdateRolePermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RBACService.update_role_permissions(db, role_id, data.permission_ids)
