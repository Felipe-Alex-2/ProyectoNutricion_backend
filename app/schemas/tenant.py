from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class TenantBase(BaseModel):
    name: str
    code: str
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = True


class TenantCreate(TenantBase):
    pass


class TenantUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    logo_url: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class TenantResponse(TenantBase):
    id: str
    created_at: datetime
    updated_at: datetime
    users_count: Optional[int] = 0

    model_config = ConfigDict(from_attributes=True)
