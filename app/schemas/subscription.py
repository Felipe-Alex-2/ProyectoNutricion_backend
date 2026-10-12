from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, field_serializer


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
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    plan_name: str
    status: str
    amount: float
    currency: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    paypal_order_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class SubscriptionHistoryOut(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    user_id: Optional[str] = None
    plan_name: str
    status: str
    amount: float
    currency: str
    started_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    paypal_order_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class VerifyOrderResponse(BaseModel):
    paid: bool
    status: str
    message: str
    subscription: Optional[SubscriptionOut] = None


class SubscriptionReceiptOut(BaseModel):
    id: str
    buyer_name: str
    buyer_email: str
    plan_name: str
    amount: float
    currency: str
    paypal_order_id: str
    paypal_capture_id: str
    is_sandbox: bool
    paid_at: datetime
    expires_at: Optional[datetime] = None
    issued_at: datetime

    model_config = ConfigDict(from_attributes=True)


    @field_serializer("paid_at", "expires_at", "issued_at")
    def serialize_utc_date(self, value):
        if value is None:
            return None
        return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()
