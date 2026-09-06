from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class ActivityLogCreate(BaseModel):
    action: str
    description: str
    category: Optional[str] = "SISTEMA"
    ip_address: Optional[str] = None


class ActivityLogResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    user_name: Optional[str] = None
    action: str
    description: str
    category: str
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
