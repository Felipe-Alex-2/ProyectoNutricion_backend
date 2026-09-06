from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict


class UserBase(BaseModel):
    email: EmailStr
    full_name: str
    phone: Optional[str] = None


class UserCreate(UserBase):
    password: str
    role_id: Optional[str] = "CLIENTE"
    tenant_id: Optional[str] = None


class OrganizationUserCreate(UserBase):
    password: str
    role_id: str  # ADMIN_ORGANIZATION, NUTRICIONISTA, CLIENTE
    tenant_id: str


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    password: Optional[str] = None
    role_id: Optional[str] = None
    tenant_id: Optional[str] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    id: str
    role_id: str
    tenant_id: Optional[str] = None
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
