"""
Subscription management endpoints.

Provides plan listing, order creation/capture (PayPal),
active subscription queries, cancellation, and payment history.
"""

from typing import List
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
#  Current subscription for the logged-in user's tenant
# ------------------------------------------------------------------ #
@router.get("/current", response_model=SubscriptionOut | None)
def get_current_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the active subscription for the user's tenant, or null."""
    if not current_user.tenant_id:
        return None
    return SubscriptionService.get_active(db, current_user.tenant_id)


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
    if not current_user.tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Tu cuenta no está asociada a una organización (tenant). Contacta al administrador.",
        )

    # Only admins can create subscriptions
    if current_user.role_id not in ("SAAS_ADMIN", "ORG_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail="Solo los administradores pueden gestionar suscripciones.",
        )

    try:
        result = SubscriptionService.create_order(db, current_user.tenant_id, body.plan_name)
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
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tu cuenta no está asociada a un tenant.")

    try:
        subscription = SubscriptionService.capture_order(db, body.order_id, current_user.tenant_id)
        return subscription
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al capturar pago: {str(e)}")


# ------------------------------------------------------------------ #
#  Cancel active subscription
# ------------------------------------------------------------------ #
@router.post("/cancel", response_model=SubscriptionOut)
def cancel_subscription(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel the active subscription for the user's tenant."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="Tu cuenta no está asociada a un tenant.")

    if current_user.role_id not in ("SAAS_ADMIN", "ORG_ADMIN"):
        raise HTTPException(status_code=403, detail="Solo los administradores pueden cancelar suscripciones.")

    try:
        return SubscriptionService.cancel(db, current_user.tenant_id)
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
    """Return the full subscription history for the user's tenant."""
    if not current_user.tenant_id:
        return []
    return SubscriptionService.get_history(db, current_user.tenant_id)
