from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class PlanFeature(BaseModel):
    text: str
    included: bool


class SubscriptionPlanOut(BaseModel):
    name: str  # BASICO, PROFESIONAL, PREMIUM
    display_name: str
    price: float
    currency: str
    period: str  # "mes"
    max_patients: int | None
    features: List[PlanFeature]
    recommended: bool = False


class CreateOrderRequest(BaseModel):
    plan_name: str  # BASICO, PROFESIONAL, PREMIUM


class CreateOrderResponse(BaseModel):
    order_id: str
    approval_url: str


class CaptureOrderRequest(BaseModel):
    order_id: str


class SubscriptionOut(BaseModel):
    id: str
    tenant_id: str
    plan_name: str
    status: str
    amount: float
    currency: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    paypal_order_id: Optional[str] = None

    class Config:
        from_attributes = True


class SubscriptionHistoryOut(BaseModel):
    id: str
    plan_name: str
    status: str
    amount: float
    currency: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    paypal_order_id: Optional[str] = None

    class Config:
        from_attributes = True
