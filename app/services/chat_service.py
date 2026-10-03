import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.clinical import PatientAnamnesis
from app.models.ai_nutrition import ChatMessage, NutritionalPlan
from app.services.gemini_service import GeminiService
from app.schemas.ai_nutrition import ChatMessageResponse, ChatHistoryResponse

logger = logging.getLogger(__name__)


class ChatService:
    """Servicio del Chatbot 'Carlitos' de apoyo nutricional al paciente."""

    EMERGENCY_KEYWORDS = [
        "desmayo",
        "desmayé",
        "dolor en el pecho",
        "dolor agudo",
        "sangrado",
        "fiebre alta",
        "anorexia",
        "bulimia",
        "vomitar",
        "pastillas para adelgazar",
    ]

    @classmethod
    def process_message(
        cls,
        db: Session,
        patient_id: str,
        user_message: str,
    ) -> ChatMessageResponse:
        """
        Procesa el mensaje del paciente, inyecta su perfil clínico en el system prompt,
        evalúa filtros de seguridad y almacena la conversación.
        """
        patient = db.query(User).filter(User.id == patient_id).first()
        if not patient:
            raise ValueError("Paciente no encontrado.")

        # Guardar mensaje del usuario
        user_chat_record = ChatMessage(
            patient_id=patient_id,
            role="user",
            content=user_message,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_chat_record)
        db.commit()

        # 1. Filtro de seguridad ética y clínica inmediata
        msg_lower = user_message.lower()
        if any(kw in msg_lower for kw in cls.EMERGENCY_KEYWORDS):
            warning_reply = (
                "⚠️ Nota médica importante: Ante síntomas agudos, desmayos, dolor o conductas de riesgo, "
                "por favor contacta de inmediato a un centro de urgencias o a tu médico especialista. "
                "Como asistente de apoyo no puedo diagnosticar ni tratar emergencias de salud."
            )
            assistant_record = ChatMessage(
                patient_id=patient_id,
                role="assistant",
                content=warning_reply,
                created_at=datetime.now(timezone.utc),
            )
            db.add(assistant_record)
            db.commit()
            db.refresh(assistant_record)
            return ChatMessageResponse.model_validate(assistant_record)

        # 2. Obtener contexto del paciente (Anamnesis y Plan Activo)
        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        active_plan = (
            db.query(NutritionalPlan)
            .filter(NutritionalPlan.patient_id == patient_id, NutritionalPlan.status == "APPROVED")
            .first()
        )

        goal = anamnesis.goal if anamnesis else "Salud general"
        allergies = anamnesis.allergies or "Ninguna"
        antecedents = anamnesis.pathologies or "Sin antecedentes relevantes"
        preferences = anamnesis.food_preferences or "Variada"
        target_kcal = active_plan.daily_calories if active_plan else (2000.0 if not anamnesis else 1800.0)

        # 3. System Prompt según requerimiento
        system_instruction = (
            "Eres Carlitos, asistente nutricional de apoyo. NO sustituyes al médico ni al nutricionista. "
            "No diagnostiques, no recetes medicamentos ni dosis, no prometas resultados milagrosos. "
            f"Perfil del paciente: objetivo={goal}; alergias={allergies}; antecedentes={antecedents}; "
            f"preferencias={preferences}; calorías objetivo={target_kcal} kcal. "
            "Si lo que pregunta contradice su objetivo o condiciones clínicas, dilo con claridad, "
            "explica amablemente el motivo científico (ej. exceso de azúcares simples, picos glucémicos, calorías) "
            "y sugiere de inmediato una alternativa saludable atractiva. "
            "Responde de forma breve, cálida y en español. "
            "Ante síntomas graves o dudas médicas, recomienda consultar a su nutricionista o médico tratante."
        )

        # 4. Contexto del historial reciente (últimos 6 mensajes)
        recent_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.patient_id == patient_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(6)
            .all()
        )
        recent_msgs.reverse()

        conversation_history_text = "\n".join(
            [f"{m.role.capitalize()}: {m.content}" for m in recent_msgs]
        )

        full_prompt = (
            f"Historial de conversación reciente:\n{conversation_history_text}\n\n"
            f"Pregunta del paciente: {user_message}\n\n"
            "Respuesta de Carlitos:"
        )

        # 5. Generar respuesta con Gemini (o fallback inteligente)
        reply_text = GeminiService.generate_text(
            prompt=full_prompt,
            system_instruction=system_instruction,
            temperature=0.3,
            max_output_tokens=600,
        )

        if not reply_text:
            reply_text = GeminiService._fallback_text_response(user_message)

        # 6. Almacenar respuesta del asistente
        assistant_record = ChatMessage(
            patient_id=patient_id,
            role="assistant",
            content=reply_text,
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_record)
        db.commit()
        db.refresh(assistant_record)

        return ChatMessageResponse.model_validate(assistant_record)

    @classmethod
    def get_history(
        cls,
        db: Session,
        patient_id: str,
        limit: int = 50,
    ) -> ChatHistoryResponse:
        """Recupera el historial de chat con Carlitos para la vista móvil."""
        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        messages = (
            db.query(ChatMessage)
            .filter(ChatMessage.patient_id == patient_id)
            .order_by(ChatMessage.created_at.asc())
            .limit(limit)
            .all()
        )
        return ChatHistoryResponse(
            patient_id=patient_id,
            patient_goal=anamnesis.goal if anamnesis else "Salud general",
            messages=[ChatMessageResponse.model_validate(m) for m in messages],
        )

    @classmethod
    def clear_history(cls, db: Session, patient_id: str) -> None:
        """Limpia el historial de chat si el paciente lo solicita."""
        db.query(ChatMessage).filter(ChatMessage.patient_id == patient_id).delete()
        db.commit()
