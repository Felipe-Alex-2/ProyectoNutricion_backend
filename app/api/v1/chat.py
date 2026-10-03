"""Endpoints del Chatbot de apoyo nutricional 'Carlitos'."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.chat_service import ChatService
from app.schemas.ai_nutrition import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatHistoryResponse,
)

router = APIRouter(prefix="/chat", tags=["Chatbot Carlitos"])


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
    """
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
    """Recupera el historial de conversación reciente con Carlitos."""
    return ChatService.get_history(db=db, patient_id=current_user.id)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Borra el historial de conversación del paciente con Carlitos."""
    ChatService.clear_history(db=db, patient_id=current_user.id)
    return None
