from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, EmailStr, field_validator


class TenantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Nombre de la clínica u organización")
    code: str = Field(..., min_length=2, max_length=50, description="Código único identificador")
    phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Teléfono de contacto")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico de contacto")
    address: Optional[str] = Field(None, max_length=255, description="Dirección física")
    logo_url: Optional[str] = Field(None, max_length=500, description="URL del logotipo")
    description: Optional[str] = Field(None, max_length=500, description="Descripción de la clínica")
    is_active: bool = Field(True, description="Estado activo de la organización")

    @field_validator("name", "code")
    @classmethod
    def validate_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("El campo no puede estar vacío ni contener solo espacios")
        return v


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100, description="Nombre de la clínica")
    phone: Optional[str] = Field(None, min_length=7, max_length=25, description="Teléfono de contacto")
    email: Optional[EmailStr] = Field(None, description="Correo electrónico")
    address: Optional[str] = Field(None, max_length=255, description="Dirección física")
    logo_url: Optional[str] = Field(None, max_length=500, description="URL del logotipo")
    description: Optional[str] = Field(None, max_length=500, description="Descripción")
    is_active: Optional[bool] = Field(None, description="Estado activo")


class TenantResponse(TenantBase):
    id: str
    created_at: datetime
    updated_at: datetime
    users_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)

