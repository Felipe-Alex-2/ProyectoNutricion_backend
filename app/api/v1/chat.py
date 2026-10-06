"""Endpoints del Chatbot de apoyo nutricional 'Carlitos'."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.services.subscription_service import SubscriptionService
from app.schemas.ai_nutrition import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
)

router = APIRouter(prefix="/chat", tags=["Chatbot Carlitos"])


def _verify_carlitos_premium_access(db: Session, user: User) -> None:
    """Verifica que el usuario cliente tenga activo el Plan Premium IA ($5 USD)."""
    if user.role_id in ["CLIENTE", "PACIENTE"]:
        active_sub = SubscriptionService.get_active(db, user_id=user.id)
        if not active_sub or active_sub.plan_name != "CLIENTE_PREMIUM":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="El Asistente Carlitos IA es exclusivo para usuarios con el Plan Premium IA ($5 USD/mes). Por favor suscríbete para acceder.",
            )


@router.post("", response_model=ChatMessageResponse)
def send_chat_message(
    data: ChatMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Envía una pregunta a Carlitos.
    El backend inyecta los antecedentes del paciente (objetivo, alergias, kcal meta),
    consulta a Gemini respetando las directrices éticas y retorna la respuesta.
    Requiere Plan Premium IA ($5 USD).
    """
    _verify_carlitos_premium_access(db, current_user)
    try:
        reply = ChatService.process_message(
            db=db,
            patient_id=current_user.id,
            user_message=data.message,
        )
        return reply
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error en el chat: {str(e)}")


@router.get("/history", response_model=ChatHistoryResponse)
def get_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recupera el historial de conversación reciente con Carlitos (requiere Premium)."""
    _verify_carlitos_premium_access(db, current_user)
    return ChatService.get_history(db=db, patient_id=current_user.id)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Borra el historial de conversación del paciente con Carlitos."""
    _verify_carlitos_premium_access(db, current_user)
    ChatService.clear_history(db=db, patient_id=current_user.id)
    return None
