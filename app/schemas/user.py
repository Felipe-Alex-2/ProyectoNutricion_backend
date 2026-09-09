from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field, field_validator


class UserBase(BaseModel):
    email: EmailStr = Field(..., description="Correo electrónico válido")
    full_name: str = Field(..., min_length=2, max_length=100, description="Nombre completo (mínimo 2 caracteres)")
    phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Teléfono de contacto")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("El nombre completo debe tener al menos 2 caracteres")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) < 7:
                raise ValueError("El teléfono debe contener al menos 7 dígitos")
        return v


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Contraseña de acceso (mínimo 8 caracteres)")
    role_id: Optional[str] = Field("CLIENTE", description="Rol asignado al usuario")
    tenant_id: Optional[str] = Field(None, description="ID de la organización asociada")


class OrganizationUserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128, description="Contraseña de acceso (mínimo 8 caracteres)")
    role_id: str = Field(..., min_length=2, max_length=50, description="Rol del usuario (ej: NUTRICIONISTA, CLIENTE, ADMIN_ORGANIZATION)")
    tenant_id: str = Field(..., min_length=1, description="ID de la organización o clínica asociada")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=100, description="Nombre completo")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico")
    phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Teléfono de contacto")
    password: Optional[str] = Field(None, min_length=8, max_length=128, description="Nueva contraseña")
    role_id: Optional[str] = Field(None, description="Rol del usuario")
    tenant_id: Optional[str] = Field(None, description="ID de la organización")
    is_active: Optional[bool] = Field(None, description="Estado de actividad")

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if len(v) < 2:
                raise ValueError("El nombre completo debe tener al menos 2 caracteres")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if not v:
                return None
            if len(v) < 7:
                raise ValueError("El teléfono debe contener al menos 7 dígitos")
        return v


class UserResponse(UserBase):
    id: str
    role_id: str
    tenant_id: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

