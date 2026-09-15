"""
Point-of-Sale Payment Service.

Manages in-branch charges/payments to clients/patients using PayPal Sandbox.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.payment import Payment
from app.models.tenant import Tenant
from app.models.user import User
from app.schemas.payment import (
    PaymentCreate,
    PaymentOrderCreatedOut,
    PaymentOut,
    PaymentStatsOut,
)
from app.services.paypal_service import PayPalService

logger = logging.getLogger("payments")


class PaymentService:

    @staticmethod
    def _map_to_out(p: Payment) -> PaymentOut:
        return PaymentOut(
            id=p.id,
            tenant_id=p.tenant_id,
            tenant_name=p.tenant.name if p.tenant else None,
            cashier_id=p.cashier_id,
            cashier_name=p.cashier.full_name if p.cashier else None,
            customer_name=p.customer_name,
            customer_email=p.customer_email,
            concept=p.concept,
            amount=p.amount,
            currency=p.currency,
            status=p.status,
            paypal_order_id=p.paypal_order_id,
            paypal_capture_id=p.paypal_capture_id,
            notes=p.notes,
            created_at=p.created_at,
            paid_at=p.paid_at,
        )

    @staticmethod
    def create_payment(
        db: Session,
        cashier: User,
        data: PaymentCreate,
        frontend_url: str = "http://localhost:4200",
    ) -> PaymentOrderCreatedOut:
        """Create a pending payment record and generate the PayPal checkout order."""
        # 1. Verify tenant exists
        tenant = db.query(Tenant).filter(Tenant.id == data.tenant_id).first()
        if not tenant:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Sucursal con ID {data.tenant_id} no encontrada",
            )

        # 2. Call PayPal Sandbox API to create order
        description = f"Cobro Sucursal {tenant.name} - {data.concept} ({data.customer_name})"
        return_url = f"{frontend_url}/paypal-return"
        cancel_url = f"{frontend_url}/dashboard"

        try:
            order_data = PayPalService.create_order(
                amount=data.amount,
                currency=data.currency,
                description=description,
                return_url=return_url,
                cancel_url=cancel_url,
            )
        except Exception as exc:
            logger.error(f"Error creando orden en PayPal Sandbox: {exc}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Error comunicando con PayPal Sandbox: {str(exc)}",
            )

        # 3. Store Payment in DB
        payment = Payment(
            tenant_id=data.tenant_id,
            cashier_id=cashier.id,
            customer_name=data.customer_name,
            customer_email=data.customer_email,
            concept=data.concept,
            amount=round(data.amount, 2),
            currency=data.currency,
            status="PENDING",
            paypal_order_id=order_data["order_id"],
            notes=data.notes,
        )
        db.add(payment)
        db.commit()
        db.refresh(payment)

        logger.info(
            f"Cobro creado: ID {payment.id}, PayPal Order {payment.paypal_order_id}, Monto ${payment.amount}"
        )

        return PaymentOrderCreatedOut(
            payment_id=payment.id,
            paypal_order_id=order_data["order_id"],
            approval_url=order_data["approval_url"],
            amount=payment.amount,
            currency=payment.currency,
            concept=payment.concept,
            customer_name=payment.customer_name,
        )

    @staticmethod
    def capture_payment(db: Session, paypal_order_id: str) -> PaymentOut:
        """Capture an approved PayPal order and mark the payment as COMPLETED."""
        payment = (
            db.query(Payment)
            .filter(Payment.paypal_order_id == paypal_order_id)
            .first()
        )
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No se encontró cobro asociado a la orden PayPal {paypal_order_id}",
            )

        if payment.status == "COMPLETED":
            return PaymentService._map_to_out(payment)

        # Capture with PayPal
        try:
            capture_res = PayPalService.capture_order(paypal_order_id)
        except Exception as exc:
            logger.error(f"Error capturando orden {paypal_order_id}: {exc}")
            payment.status = "FAILED"
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Fallo en la captura de fondos con PayPal: {str(exc)}",
            )

        payment.status = "COMPLETED"
        payment.paid_at = datetime.now(timezone.utc)
        payment.paypal_capture_id = capture_res.get("capture_id")

        db.commit()
        db.refresh(payment)

        logger.info(f"Cobro completado exitosamente: ID {payment.id}, Monto ${payment.amount}")
        return PaymentService._map_to_out(payment)

    @staticmethod
    def list_payments(
        db: Session,
        tenant_id: Optional[str] = None,
        status_filter: Optional[str] = None,
    ) -> List[PaymentOut]:
        """List payments filtered by tenant branch and optional status."""
        query = db.query(Payment)
        if tenant_id:
            query = query.filter(Payment.tenant_id == tenant_id)
        if status_filter:
            query = query.filter(Payment.status == status_filter)

        payments = query.order_by(Payment.created_at.desc()).all()
        return [PaymentService._map_to_out(p) for p in payments]

    @staticmethod
    def get_payment_stats(db: Session, tenant_id: Optional[str] = None) -> PaymentStatsOut:
        """Calculate summary statistics for a given branch or all branches."""
        query = db.query(Payment)
        if tenant_id:
            query = query.filter(Payment.tenant_id == tenant_id)

        all_payments = query.all()
        total_collected = sum(p.amount for p in all_payments if p.status == "COMPLETED")
        completed_count = sum(1 for p in all_payments if p.status == "COMPLETED")
        pending_count = sum(1 for p in all_payments if p.status == "PENDING")

        return PaymentStatsOut(
            total_collected=round(total_collected, 2),
            total_count=len(all_payments),
            completed_count=completed_count,
            pending_count=pending_count,
        )

    @staticmethod
    def cancel_payment(db: Session, payment_id: str) -> PaymentOut:
        """Cancel a pending payment."""
        payment = db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cobro no encontrado",
            )
        if payment.status == "COMPLETED":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede cancelar un cobro ya completado.",
            )

        payment.status = "CANCELLED"
        db.commit()
        db.refresh(payment)
        return PaymentService._map_to_out(payment)
