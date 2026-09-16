"""
Subscription business logic.

Manages plan definitions, order lifecycle (create → capture → activate),
and subscription queries.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.subscription import Subscription
from app.schemas.subscription import PlanFeature, SubscriptionPlanOut
from app.services.paypal_service import PayPalService
from app.config import settings

logger = logging.getLogger("subscriptions")

# ------------------------------------------------------------------ #
#  Plan catalogue — kept in code for simplicity (could move to DB)
# ------------------------------------------------------------------ #

PLANS = {
    "CLIENTE_FREE": {
        "display_name": "Plan Gratuito",
        "price": 0.0,
        "currency": "USD",
        "period": "siempre",
        "max_patients": None,
        "recommended": False,
        "features": [
            {"text": "Mi Ficha de Salud (Anamnesis)", "included": True},
            {"text": "Generar Cita con Nutricionista", "included": True},
            {"text": "Vincularse con Nutricionista", "included": True},
            {"text": "Ver Plan Nutricional", "included": True},
            {"text": "Recomendación de comidas con IA", "included": False},
            {"text": "Estimación nutricional de Alimentos con IA", "included": False},
        ],
    },
    "CLIENTE_PREMIUM": {
        "display_name": "Plan Premium IA",
        "price": 5.0,
        "currency": "USD",
        "period": "mes",
        "max_patients": None,
        "recommended": True,
        "features": [
            {"text": "Mi Ficha de Salud (Anamnesis)", "included": True},
            {"text": "Generar Cita con Nutricionista", "included": True},
            {"text": "Vincularse con Nutricionista", "included": True},
            {"text": "Ver Plan Nutricional", "included": True},
            {"text": "Recomendación de comidas con IA", "included": True},
            {"text": "Estimación nutricional de Alimentos con IA", "included": True},
        ],
    },
    "BASICO": {
        "display_name": "Básico",
        "price": 9.99,
        "currency": "USD",
        "period": "mes",
        "max_patients": 10,
        "recommended": False,
        "features": [
            {"text": "Hasta 10 pacientes", "included": True},
            {"text": "Vinculación WhatsApp", "included": True},
            {"text": "Bitácora de actividades", "included": True},
            {"text": "Recetario & Macros", "included": False},
            {"text": "Historial Clínico", "included": False},
            {"text": "Soporte prioritario", "included": False},
        ],
    },
    "PROFESIONAL": {
        "display_name": "Profesional",
        "price": 24.99,
        "currency": "USD",
        "period": "mes",
        "max_patients": 50,
        "recommended": True,
        "features": [
            {"text": "Hasta 50 pacientes", "included": True},
            {"text": "Vinculación WhatsApp", "included": True},
            {"text": "Bitácora de actividades", "included": True},
            {"text": "Recetario & Macros", "included": True},
            {"text": "Historial Clínico", "included": True},
            {"text": "Soporte prioritario", "included": False},
        ],
    },
    "PREMIUM": {
        "display_name": "Premium",
        "price": 49.99,
        "currency": "USD",
        "period": "mes",
        "max_patients": None,
        "recommended": False,
        "features": [
            {"text": "Pacientes ilimitados", "included": True},
            {"text": "Vinculación WhatsApp", "included": True},
            {"text": "Bitácora de actividades", "included": True},
            {"text": "Recetario & Macros", "included": True},
            {"text": "Historial Clínico", "included": True},
            {"text": "Soporte prioritario", "included": True},
        ],
    },
}


class SubscriptionService:

    # ------------------------------------------------------------------ #
    #  Read plans
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_plans() -> List[SubscriptionPlanOut]:
        """Return all available subscription plans."""
        result: List[SubscriptionPlanOut] = []
        for name, info in PLANS.items():
            result.append(
                SubscriptionPlanOut(
                    name=name,
                    display_name=info["display_name"],
                    price=info["price"],
                    currency=info["currency"],
                    period=info["period"],
                    max_patients=info["max_patients"],
                    recommended=info["recommended"],
                    features=[PlanFeature(**f) for f in info["features"]],
                )
            )
        return result

    # ------------------------------------------------------------------ #
    #  Create order (pending subscription)
    # ------------------------------------------------------------------ #
    @staticmethod
    def create_order(
        db: Session,
        tenant_id: Optional[str],
        plan_name: str,
        user_id: Optional[str] = None,
    ) -> dict:
        """Create a PayPal order and a PENDING subscription row."""
        plan_name_upper = plan_name.upper()
        if plan_name_upper not in PLANS:
            raise ValueError(f"Plan '{plan_name}' no existe. Opciones: {list(PLANS.keys())}")

        plan = PLANS[plan_name_upper]

        # Build return URL — use frontend URL from settings
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        return_url = f"{frontend_url}/paypal-return"
        cancel_url = f"{frontend_url}/dashboard"

        # Call PayPal
        paypal_result = PayPalService.create_order(
            amount=plan["price"],
            currency=plan["currency"],
            description=f"NutriSalud — Plan {plan['display_name']} (1 Mes)",
            return_url=return_url,
            cancel_url=cancel_url,
        )

        # Persist pending subscription
        subscription = Subscription(
            tenant_id=tenant_id,
            user_id=user_id,
            plan_name=plan_name_upper,
            paypal_order_id=paypal_result["order_id"],
            status="PENDING",
            amount=plan["price"],
            currency=plan["currency"],
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        logger.info(
            f"Subscription order created: {subscription.id} "
            f"(tenant={tenant_id}, user={user_id}, plan={plan_name_upper}, paypal_order={paypal_result['order_id']})"
        )

        return {
            "order_id": paypal_result["order_id"],
            "approval_url": paypal_result["approval_url"],
            "subscription_id": subscription.id,
        }

    # ------------------------------------------------------------------ #
    #  Capture payment and activate subscription
    # ------------------------------------------------------------------ #
    @staticmethod
    def capture_order(
        db: Session,
        order_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Subscription:
        """
        Capture a PayPal order after buyer approval.
        Activates the subscription and sets expiry to +30 days.
        """
        query = db.query(Subscription).filter(
            Subscription.paypal_order_id == order_id,
            Subscription.status == "PENDING",
        )
        if tenant_id:
            query = query.filter(Subscription.tenant_id == tenant_id)
        elif user_id:
            query = query.filter(Subscription.user_id == user_id)

        subscription = query.first()
        if not subscription:
            raise ValueError("No se encontró una suscripción pendiente para esta orden.")

        # Capture with PayPal
        capture_result = PayPalService.capture_order(order_id)
        if capture_result.get("status") not in ("COMPLETED", "APPROVED"):
            subscription.status = "FAILED"  # type: ignore[assignment]
            db.commit()
            raise Exception(
                f"El pago no fue completado. Estado PayPal: {capture_result.get('status')}"
            )

        # Cancel any previously active subscription for this tenant or user
        cancel_query = db.query(Subscription).filter(Subscription.status == "ACTIVE")
        if subscription.tenant_id:
            cancel_query = cancel_query.filter(Subscription.tenant_id == subscription.tenant_id)
        elif subscription.user_id:
            cancel_query = cancel_query.filter(Subscription.user_id == subscription.user_id)
        cancel_query.update({"status": "REPLACED"})

        # Activate
        now = datetime.now(timezone.utc)
        subscription.paypal_capture_id = capture_result.get("capture_id")  # type: ignore[assignment]
        subscription.status = "ACTIVE"  # type: ignore[assignment]
        subscription.started_at = now  # type: ignore[assignment]
        subscription.expires_at = now + timedelta(days=30)  # type: ignore[assignment]
        db.commit()
        db.refresh(subscription)

        logger.info(
            f"Subscription activated: {subscription.id} "
            f"(tenant={subscription.tenant_id}, user={subscription.user_id}, plan={subscription.plan_name}, expires={subscription.expires_at})"
        )
        return subscription

    # ------------------------------------------------------------------ #
    #  Direct / Sandbox activation for testing
    # ------------------------------------------------------------------ #
    @staticmethod
    def direct_activate_client_premium(db: Session, user_id: str, order_id: Optional[str] = None) -> Subscription:
        """Directly activates or validates a 30-day Premium subscription for a client."""
        # Check if there is an existing pending subscription for this user
        subscription = None
        if order_id:
            subscription = db.query(Subscription).filter(
                Subscription.paypal_order_id == order_id,
                Subscription.user_id == user_id,
            ).first()

        now = datetime.now(timezone.utc)
        # Cancel any existing active
        db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "ACTIVE",
        ).update({"status": "REPLACED"})

        if subscription:
            subscription.status = "ACTIVE"
            subscription.started_at = now
            subscription.expires_at = now + timedelta(days=30)
            subscription.amount = 5.0
            subscription.currency = "USD"
        else:
            subscription = Subscription(
                user_id=user_id,
                plan_name="CLIENTE_PREMIUM",
                paypal_order_id=order_id or "DIRECT_SANDBOX",
                paypal_capture_id="SANDBOX_VERIFIED",
                status="ACTIVE",
                amount=5.0,
                currency="USD",
                started_at=now,
                expires_at=now + timedelta(days=30),
            )
            db.add(subscription)

        db.commit()
        db.refresh(subscription)
        return subscription

    # ------------------------------------------------------------------ #
    #  Query helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def get_active(
        db: Session,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[Subscription]:
        """Return the currently active subscription for a tenant or user, or None."""
        query = db.query(Subscription).filter(Subscription.status == "ACTIVE")
        if user_id:
            query = query.filter(Subscription.user_id == user_id)
        elif tenant_id:
            query = query.filter(Subscription.tenant_id == tenant_id)
        else:
            return None

        return query.order_by(Subscription.created_at.desc()).first()

    @staticmethod
    def get_history(
        db: Session,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Subscription]:
        """Return all subscriptions for a tenant or user, newest first."""
        query = db.query(Subscription)
        if user_id:
            query = query.filter(Subscription.user_id == user_id)
        elif tenant_id:
            query = query.filter(Subscription.tenant_id == tenant_id)
        else:
            return []
        return query.order_by(Subscription.created_at.desc()).all()

    @staticmethod
    def cancel(
        db: Session,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Subscription:
        """Cancel the active subscription for a tenant or user."""
        subscription = SubscriptionService.get_active(db, tenant_id=tenant_id, user_id=user_id)
        if not subscription:
            raise ValueError("No hay una suscripción activa para cancelar.")

        subscription.status = "CANCELLED"  # type: ignore[assignment]
        db.commit()
        db.refresh(subscription)

        logger.info(f"Subscription cancelled: {subscription.id} (tenant={tenant_id}, user={user_id})")
        return subscription
