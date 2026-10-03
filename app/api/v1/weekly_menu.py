"""Endpoints para generación y consulta del Menú Semanal."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.ai_nutrition import NutritionalPlan
from app.services.ai_plan_service import AIPlanService
from app.schemas.ai_nutrition import WeeklyMenuGenerateRequest, WeeklyMenuResponse

router = APIRouter(prefix="/menu-semanal", tags=["Menú Semanal"])


@router.post("/generate", response_model=WeeklyMenuResponse)
def generate_weekly_menu(
    data: WeeklyMenuGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera el menú semanal de 7 días.
    REGLA: El paciente debe estar vinculado a un nutricionista y poseer un plan nutricional aprobado.
    """
    # Si es paciente, solo puede solicitar para sí mismo
    if current_user.role_id in ["CLIENTE", "PACIENTE"] and current_user.id != data.patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes solicitar menús para otro usuario.")

    try:
        response = AIPlanService.generate_weekly_menu(
            db=db,
            patient_id=data.patient_id,
            special_instructions=data.special_instructions,
        )
        return response
    except PermissionError as pe:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error al generar menú: {str(e)}")


@router.get("/current", response_model=Optional[WeeklyMenuResponse])
def get_current_weekly_menu(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Obtiene el menú semanal vigente si ya fue generado para el plan aprobado actual."""
    plan = (
        db.query(NutritionalPlan)
        .filter(NutritionalPlan.patient_id == current_user.id, NutritionalPlan.status == "APPROVED")
        .order_by(NutritionalPlan.approved_at.desc())
        .first()
    )

    if not plan or not plan.weekly_menu_json:
        return None

    import json
    from app.schemas.ai_nutrition import DayMenu
    try:
        days_data = json.loads(plan.weekly_menu_json)
        days = [DayMenu(**d) for d in days_data]
        return WeeklyMenuResponse(
            patient_id=current_user.id,
            nutritionist_id=plan.nutritionist_id,
            plan_id=plan.id,
            days=days,
            excluded_allergens=[],
            generated_at=plan.updated_at,
        )
    except Exception:
        return None
