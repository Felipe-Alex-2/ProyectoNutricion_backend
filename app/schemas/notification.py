from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: str
    user_id: str
    tenant_id: Optional[str] = None
    title: str
    message: str
    type: str
    reference_id: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationCountOut(BaseModel):
    unread_count: int
