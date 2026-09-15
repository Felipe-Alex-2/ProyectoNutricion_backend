"""
Point-of-Sale Payments Router (Caja y Cobros con PayPal Sandbox).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.payment import (
    PaymentCaptureRequest,
    PaymentCreate,
    PaymentOrderCreatedOut,
    PaymentOut,
    PaymentStatsOut,
)
from app.services.payment_service import PaymentService

router = APIRouter(prefix="/payments", tags=["Payments POS"])


@router.post("/create", response_model=PaymentOrderCreatedOut)
def create_pos_payment(
    body: PaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Crea una orden de cobro en caja e inicia el checkout de PayPal Sandbox.
    Retorna la URL de PayPal (approval_url) para realizar el pago.
    """
    # Detect frontend origin if available
    frontend_url = request.headers.get("origin") or "http://localhost:4200"

    return PaymentService.create_payment(
        db=db,
        cashier=current_user,
        data=body,
        frontend_url=frontend_url,
    )


@router.post("/capture", response_model=PaymentOut)
def capture_pos_payment(
    body: PaymentCaptureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Captura y confirma el cobro tras la aprobación del cliente en PayPal Sandbox.
    """
    return PaymentService.capture_payment(
        db=db,
        paypal_order_id=body.paypal_order_id,
    )


@router.get("", response_model=List[PaymentOut])
def list_payments(
    tenant_id: Optional[str] = Query(None, description="Filtrar por ID de sucursal"),
    status: Optional[str] = Query(None, description="Filtrar por estado (PENDING, COMPLETED, CANCELLED)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista el historial de cobros realizados en la sucursal seleccionada o general.
    """
    # Si el usuario es ADMIN_ORGANIZATION o NUTRICIONISTA y tiene tenant_id, filtrar por defecto si no es SAAS
    effective_tenant_id = tenant_id
    if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
        effective_tenant_id = current_user.tenant_id

    return PaymentService.list_payments(
        db=db,
        tenant_id=effective_tenant_id,
        status_filter=status,
    )


@router.get("/stats", response_model=PaymentStatsOut)
def get_payment_stats(
    tenant_id: Optional[str] = Query(None, description="Filtrar estadísticas por ID de sucursal"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Retorna métricas de caja (total recaudado, cobros completados y pendientes).
    """
    effective_tenant_id = tenant_id
    if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
        effective_tenant_id = current_user.tenant_id

    return PaymentService.get_payment_stats(
        db=db,
        tenant_id=effective_tenant_id,
    )


@router.post("/{payment_id}/cancel", response_model=PaymentOut)
def cancel_payment(
    payment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancela un cobro pendiente en caja.
    """
    return PaymentService.cancel_payment(
        db=db,
        payment_id=payment_id,
    )
