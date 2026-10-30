from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.user import UserResponse, UserUpdate, ProfileUpdate
from app.core.authorization import require_patient_access, require_tenant
from app.schemas.common import MessageResponse
from app.services.user_service import UserService
from app.api.deps import get_current_user
from app.core.exceptions import ConflictException, NotFoundException, ForbiddenException

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns the profile information of the currently authenticated user.",
)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update current user profile",
    description="Updates the profile details (name, email, password or developer key) of the authenticated user.",
)
def update_me(
    request: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.email and request.email.lower().strip() != current_user.email:
        existing = UserService.get_by_email(db, request.email)
        if existing:
            raise ConflictException(detail="Email is already taken by another account")

    updated_user = UserService.update(db, current_user, request)

    # Bitácora
    action_desc = "Actualización de datos de perfil"
    if request.developer_key is not None:
        action_desc += " y actualización de llave de seguridad para bitácora"
    try:
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="PERFIL_ACTUALIZADO",
            description=action_desc,
            category="USER",
        ))
        db.commit()
    except Exception:
        pass

    return updated_user


# =====================================================================
# GESTIÓN DE CLIENTES / PACIENTES (LISTAR, EDITAR, ELIMINAR/DESACTIVAR)
# =====================================================================

@router.get(
    "/patients",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="Listar clientes/pacientes",
)
def list_patients(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Búsqueda por nombre, correo o teléfono"),
    is_active: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    tenant_id: Optional[str] = Query(None, description="Filtrar por organización / tenant (SUPERADMIN)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retorna la lista de pacientes accesibles según el rol del usuario."""
    if current_user.role_id not in ["SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise ForbiddenException("No tienes permisos para consultar la lista de clientes.")

    if current_user.role_id != "SUPERADMIN":
        require_tenant(current_user, current_user.tenant_id)
    tenant_filter = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else tenant_id
    patients = UserService.list_patients(
        db,
        tenant_id=tenant_filter,
        search=search,
        is_active=is_active,
        nutritionist_id=current_user.id if current_user.role_id == "NUTRICIONISTA" else None,
        limit=limit, offset=offset,
    )
    return patients


@router.put(
    "/patients/{patient_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Editar información de un cliente/paciente",
)
def update_patient(
    patient_id: str,
    data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_patient_access(db, current_user, patient_id)
    if (data.password or data.developer_key) and current_user.role_id != "SUPERADMIN":
        raise ForbiddenException("Solo administración global puede restablecer credenciales.")
    """Permite al especialista o administrador actualizar datos de contacto de un cliente."""
    if current_user.role_id not in ["SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise ForbiddenException("No tienes permisos para modificar datos de clientes.")

    patient = UserService.get_by_id(db, patient_id)
    if not patient or patient.role_id != "CLIENTE":
        raise NotFoundException("Cliente no encontrado.")

    if current_user.role_id == "ADMIN_ORGANIZATION" and patient.tenant_id != current_user.tenant_id:
        raise ForbiddenException("El cliente no pertenece a tu clínica u organización.")

    if data.email and data.email.lower().strip() != patient.email:
        existing = UserService.get_by_email(db, data.email)
        if existing and existing.id != patient.id:
            raise ConflictException("El correo ya se encuentra registrado por otro usuario.")

    updated = UserService.update(db, patient, data)

    # Auditoría
    try:
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="CLIENTE_ACTUALIZADO",
            description=f"Se actualizaron los datos del cliente '{patient.full_name}' ({patient.email}).",
            category="PATIENT_MANAGEMENT",
        ))
        db.commit()
    except Exception:
        pass

    return updated


@router.delete(
    "/patients/{patient_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Desactivar o eliminar cliente",
)
def delete_patient(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_patient_access(db, current_user, patient_id)
    """Desactiva un cliente y anula sus vinculaciones activas."""
    if current_user.role_id not in ["SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise ForbiddenException("No tienes permisos para desactivar clientes.")

    patient = UserService.get_by_id(db, patient_id)
    if not patient or patient.role_id != "CLIENTE":
        raise NotFoundException("Cliente no encontrado.")

    if current_user.role_id == "ADMIN_ORGANIZATION" and patient.tenant_id != current_user.tenant_id:
        raise ForbiddenException("El cliente no pertenece a tu clínica u organización.")

    success = UserService.deactivate_patient(db, patient_id)
    if not success:
        raise NotFoundException("No se pudo desactivar el cliente.")

    # Auditoría
    try:
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="CLIENTE_DESACTIVADO",
            description=f"Se desactivó al cliente '{patient.full_name}' ({patient.email}) y se desvincularon sus accesos.",
            category="PATIENT_MANAGEMENT",
        ))
        db.commit()
    except Exception:
        pass

    return MessageResponse(message=f"Cliente '{patient.full_name}' desactivado y desvinculado con éxito.")
