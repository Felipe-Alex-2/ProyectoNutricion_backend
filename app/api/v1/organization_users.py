from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.user import UserResponse, OrganizationUserCreate, UserUpdate
from app.core.security import get_password_hash
from app.core.exceptions import (
    BadRequestException,
    ConflictException,
    ForbiddenException,
    NotFoundException,
)

router = APIRouter(prefix="/organization-users", tags=["Usuarios de Organización"])


@router.get("", response_model=List[UserResponse])
def list_organization_users(
    tenant_id: Optional[str] = Query(None),
    role_id: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(User)

    # Aislamiento multi-tenant:
    # Si es ADMIN_ORGANIZATION, solo puede ver usuarios de su propia organización
    if current_user.role_id == "ADMIN_ORGANIZATION":
        if not current_user.tenant_id:
            return []
        query = query.filter(User.tenant_id == current_user.tenant_id)
    elif current_user.role_id == "ADMIN_SAAS":
        # Admin SaaS puede ver todos o filtrar por organización
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
    else:
        # Otros roles (Nutricionista / Cliente) solo ven su propia clínica
        if current_user.tenant_id:
            query = query.filter(User.tenant_id == current_user.tenant_id)
        else:
            query = query.filter(User.id == current_user.id)

    if role_id:
        query = query.filter(User.role_id == role_id)

    if q:
        search = f"%{q.strip()}%"
        query = query.filter((User.full_name.ilike(search)) | (User.email.ilike(search)))

    return query.order_by(User.created_at.desc()).all()


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_organization_user(
    data: OrganizationUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Aislamiento multi-tenant:
    # Si es Admin de Organización, solo puede registrar usuarios en su propia clínica
    target_tenant_id = data.tenant_id
    if current_user.role_id == "ADMIN_ORGANIZATION":
        if not current_user.tenant_id:
            raise ForbiddenException("Tu cuenta no tiene una organización asignada.")
        target_tenant_id = current_user.tenant_id
        if data.role_id == "ADMIN_SAAS":
            raise ForbiddenException("No tienes autorización para asignar el rol de Administrador SaaS Global.")

    # Check email unique
    clean_email = data.email.strip().lower()
    existing = db.query(User).filter(User.email == clean_email).first()
    if existing:
        raise ConflictException(f"El correo '{clean_email}' ya está registrado")

    # Check name unique within tenant (máx 250 car ya validado en schema)
    clean_name = data.full_name.strip()
    existing_name = db.query(User).filter(
        func.lower(User.full_name) == clean_name.lower(),
        User.tenant_id == target_tenant_id,
        User.is_active == True,
    ).first()
    if existing_name:
        raise ConflictException(f"Ya existe un usuario con el nombre '{clean_name}' en esta organización. No se puede repetir el mismo nombre.")

    # Check tenant exists
    tenant = db.query(Tenant).filter(Tenant.id == target_tenant_id).first()
    if not tenant:
        raise NotFoundException("La organización seleccionada no existe")

    user = User(
        email=clean_email,
        full_name=clean_name,
        hashed_password=get_password_hash(data.password),
        phone=data.phone.strip() if data.phone else None,
        role_id=data.role_id,
        tenant_id=target_tenant_id,
        is_active=True,
        is_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.put("/{user_id}", response_model=UserResponse)
def update_organization_user(
    user_id: str,
    data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("Usuario no encontrado")

    # Aislamiento multi-tenant:
    # Si es Admin de Organización, no puede modificar usuarios de otra clínica
    if current_user.role_id == "ADMIN_ORGANIZATION":
        if user.tenant_id != current_user.tenant_id:
            raise ForbiddenException("No tienes permiso para gestionar usuarios de otra organización.")
        if data.role_id == "ADMIN_SAAS":
            raise ForbiddenException("No puedes ascender a un usuario a Administrador SaaS Global.")
        # No permitir mover a otra organización
        data.tenant_id = current_user.tenant_id

    if data.full_name is not None:
        clean_name = data.full_name.strip()
        existing_name = db.query(User).filter(
            func.lower(User.full_name) == clean_name.lower(),
            User.tenant_id == user.tenant_id,
            User.is_active == True,
            User.id != user.id,
        ).first()
        if existing_name:
            raise ConflictException(f"Ya existe otro usuario activo con el nombre '{clean_name}' en esta organización. No se puede repetir el mismo nombre.")
        user.full_name = clean_name
    if data.phone is not None:
        user.phone = data.phone.strip() if data.phone else None
    if data.role_id is not None:
        user.role_id = data.role_id
    if data.tenant_id is not None and current_user.role_id == "ADMIN_SAAS":
        user.tenant_id = data.tenant_id
    if data.is_active is not None:
        user.is_active = data.is_active

    # Modificación de contraseña: Solo Administrador SaaS Global
    if data.password:
        if current_user.role_id != "ADMIN_SAAS":
            raise ForbiddenException(
                "Solo el Administrador SaaS (Admin Global) tiene permisos para modificar contraseñas de usuarios."
            )
        user.hashed_password = get_password_hash(data.password)

    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/toggle-status", response_model=UserResponse)
def toggle_user_status(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("Usuario no encontrado")

    if current_user.role_id == "ADMIN_ORGANIZATION" and user.tenant_id != current_user.tenant_id:
        raise ForbiddenException("No tienes permiso para modificar usuarios de otra organización.")

    if user.id == current_user.id:
        raise BadRequestException("No puedes desactivar tu propia cuenta en sesión activa.")

    user.is_active = not user.is_active
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_organization_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise NotFoundException("Usuario no encontrado")

    # Aislamiento multi-tenant:
    if current_user.role_id == "ADMIN_ORGANIZATION" and user.tenant_id != current_user.tenant_id:
        raise ForbiddenException("No tienes permiso para eliminar usuarios de otra organización.")

    if user.id == current_user.id:
        raise BadRequestException("No puedes eliminar tu propia cuenta mientras estás conectado.")

    db.delete(user)
    db.commit()
    return None
