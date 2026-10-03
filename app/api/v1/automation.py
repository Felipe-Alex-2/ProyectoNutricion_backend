"""Endpoints de Automatización (RPA), Notificaciones Inteligentes y Sistema Experto."""
from typing import Any, Dict, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.clinical import PatientAnamnesis
from app.models.ai_nutrition import AutomationConfig, ConditionCatalog
from app.services.automation_service import AutomationService
from app.services.expert_system_service import ExpertSystemService
from app.schemas.ai_nutrition import (
    AutomationConfigResponse,
    AutomationConfigUpdate,
    DeviceTokenCreate,
    HabitEvaluationResult,
    ConditionCatalogItem,
)

router = APIRouter(prefix="/automation", tags=["Automatización y RPA con IA"])


@router.post("/check-appointments")
def trigger_appointment_reminders(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ejecuta la revisión y envío de recordatorios de citas próximas en 1 hora."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a tareas de sistema.")

    return AutomationService.check_appointment_reminders(db)


@router.post("/weekly-habits")
def trigger_weekly_habits_evaluation(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Ejecuta la evaluación semanal de hábitos para todos los pacientes y genera notificaciones."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a tareas de sistema.")

    return AutomationService.run_weekly_habits_evaluation(db)


@router.post("/nutritionist-summary")
def trigger_nutritionist_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Genera y envía el resumen semanal de pacientes asignados a los nutricionistas."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado a tareas de sistema.")

    nutri_id = current_user.id if current_user.role_id == "NUTRICIONISTA" else None
    return AutomationService.generate_nutritionist_summary(db, nutritionist_id=nutri_id)


@router.get("/habits/evaluate-me", response_model=HabitEvaluationResult)
def evaluate_my_habits(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El paciente evalúa en tiempo real su cumplimiento de hábitos saludables."""
    anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == current_user.id).first()
    if not anamnesis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Completa tu anamnesis primero.")

    return ExpertSystemService.evaluate_weekly_habits(db, anamnesis, current_user.full_name)


@router.post("/device-tokens")
def register_device_token(
    data: DeviceTokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Registra el token FCM del dispositivo para notificaciones push."""
    token = AutomationService.register_device_token(
        db=db,
        user_id=current_user.id,
        token=data.token,
        platform=data.platform,
    )
    return {"status": "registered", "token_id": token.id}


@router.get("/conditions-catalog", response_model=List[ConditionCatalogItem])
def get_conditions_catalog(
    db: Session = Depends(get_db),
):
    """Lista las condiciones y alérgenos clínicos catalogados para formularios."""
    # Asegurar catálogo sembrado
    ExpertSystemService.seed_default_expert_data(db)
    items = db.query(ConditionCatalog).all()
    return items
