from datetime import datetime
from typing import List, Optional
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


class NotificationCreate(BaseModel):
    user_id: str
    title: str
    message: str
    type: str = "SISTEMA"
    reference_id: Optional[str] = None


class BroadcastNotificationCreate(BaseModel):
    title: str
    message: str
    type: str = "SEGUIMIENTO_DIETA"
    patient_ids: Optional[List[str]] = None
    reference_id: Optional[str] = None


class BroadcastNotificationOut(BaseModel):
    sent_count: int
    message: str
