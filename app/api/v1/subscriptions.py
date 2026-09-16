"""
Subscription management endpoints.

Provides plan listing, order creation/capture (PayPal),
active subscription queries, cancellation, and payment history.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.subscription import (
    CreateOrderRequest,
    CreateOrderResponse,
    CaptureOrderRequest,
    SubscriptionHistoryOut,
    SubscriptionOut,
    SubscriptionPlanOut,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ------------------------------------------------------------------ #
#  Public — list available plans
# ------------------------------------------------------------------ #
@router.get("/plans", response_model=List[SubscriptionPlanOut])
def list_plans():
    """Return the catalogue of subscription plans (no auth required)."""
    return SubscriptionService.get_plans()


# ------------------------------------------------------------------ #
#  Current subscription for the logged-in user or user's tenant
# ------------------------------------------------------------------ #
@router.get("/current", response_model=SubscriptionOut | None)
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active subscription for the user or user's tenant, or null."""
    # Check user-level subscription first (Mobile Patient)
    active_sub = SubscriptionService.get_active(db, user_id=current_user.id)
    if active_sub:
        return active_sub

    # If tenant exists, check tenant-level subscription (SaaS Admin)
    if current_user.tenant_id:
        return SubscriptionService.get_active(db, tenant_id=current_user.tenant_id)

    return None


# ------------------------------------------------------------------ #
#  Create a PayPal order (start checkout)
# ------------------------------------------------------------------ #
@router.post("/create-order", response_model=CreateOrderResponse)
def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a PayPal checkout order for the given plan."""
    # Determine if it's a client or admin plan
    plan_name = body.plan_name.upper()
    is_client_plan = plan_name.startswith("CLIENTE")

    tenant_id = current_user.tenant_id
    user_id = current_user.id

    if not is_client_plan:
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="Tu cuenta no está asociada a una organización (tenant). Contacta al administrador.",
            )
        if current_user.role_id not in ("SAAS_ADMIN", "ORG_ADMIN"):
            raise HTTPException(
                status_code=403,
                detail="Solo los administradores pueden gestionar suscripciones corporativas.",
            )

    try:
        result = SubscriptionService.create_order(
            db,
            tenant_id=tenant_id,
            plan_name=body.plan_name,
            user_id=user_id,
        )
        return CreateOrderResponse(
            order_id=result["order_id"],
            approval_url=result["approval_url"],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error con PayPal: {str(e)}")


# ------------------------------------------------------------------ #
#  Capture order (finalize payment after buyer approval)
# ------------------------------------------------------------------ #
@router.post("/capture", response_model=SubscriptionOut)
def capture_order(
    body: CaptureOrderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Capture a PayPal order after the buyer approved the checkout."""
    try:
        subscription = SubscriptionService.capture_order(
            db,
            body.order_id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        )
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al capturar pago: {str(e)}")


# ------------------------------------------------------------------ #
#  Direct Sandbox validation / activation (for testing mobile flows)
# ------------------------------------------------------------------ #
@router.post("/validate-sandbox", response_model=SubscriptionOut)
def validate_sandbox_subscription(
    order_id: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Validate and activate Premium directly in Sandbox environment."""
    sub = SubscriptionService.direct_activate_client_premium(
        db,
        user_id=current_user.id,
        order_id=order_id,
    )
    return sub


# ------------------------------------------------------------------ #
#  Cancel active subscription
# ------------------------------------------------------------------ #
@router.post("/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel the active subscription."""
    try:
        return SubscriptionService.cancel(
            db,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ------------------------------------------------------------------ #
#  Payment history
# ------------------------------------------------------------------ #
@router.get("/history", response_model=List[SubscriptionHistoryOut])
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the full subscription history for the user or tenant."""
    return SubscriptionService.get_history(
        db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
    )
