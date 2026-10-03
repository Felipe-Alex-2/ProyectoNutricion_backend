"""Endpoints de generación, edición y aprobación de Planes Nutricionales."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.ai_nutrition import NutritionalPlan
from app.services.ai_plan_service import AIPlanService
from app.schemas.ai_nutrition import (
    NutritionalPlanResponse,
    PlanGenerateRequest,
    NutritionalPlanUpdate,
)

router = APIRouter(prefix="/plans", tags=["Planes Nutricionales IA"])


@router.post("/generate-draft", response_model=NutritionalPlanResponse, status_code=status.HTTP_201_CREATED)
def generate_plan_draft(
    data: PlanGenerateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Genera un borrador de plan nutricional determinístico + IA (Mifflin-St Jeor + Gemini + filtro de exclusiones).
    Accesible para nutricionistas, admins y el propio paciente.
    """
    # Si es paciente, solo puede solicitar para sí mismo
    if current_user.role_id in ["CLIENTE", "PACIENTE"] and current_user.id != data.patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No puedes generar planes para otro usuario.")

    nutritionist_id = current_user.id if current_user.role_id in ["NUTRICIONISTA", "ADMIN_ORGANIZATION", "ADMIN_SAAS"] else None

    try:
        plan = AIPlanService.generate_plan_draft(
            db=db,
            patient_id=data.patient_id,
            nutritionist_id=nutritionist_id,
            custom_goal=data.custom_goal,
            calorie_adjustment_pct=data.calorie_adjustment_pct,
            meals_per_day=data.meals_per_day or 4,
        )
        return plan
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando plan: {str(e)}")


@router.put("/{plan_id}", response_model=NutritionalPlanResponse)
def update_plan(
    plan_id: str,
    data: NutritionalPlanUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El Nutricionista edita las calorías, macronutrientes, notas o comidas del plan."""
    if current_user.role_id not in ["NUTRICIONISTA", "ADMIN_ORGANIZATION", "ADMIN_SAAS"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo profesionales pueden editar planes nutricionales.")

    try:
        plan = AIPlanService.update_plan(
            db=db,
            plan_id=plan_id,
            title=data.title,
            daily_calories=data.daily_calories,
            protein_g=data.protein_g,
            carbs_g=data.carbs_g,
            fats_g=data.fats_g,
            meals=data.meals,
            clinical_notes=data.clinical_notes,
            status=data.status,
        )
        return plan
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{plan_id}/approve", response_model=NutritionalPlanResponse)
def approve_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El Nutricionista aprueba el plan, activándolo para el paciente."""
    if current_user.role_id not in ["NUTRICIONISTA", "ADMIN_ORGANIZATION", "ADMIN_SAAS"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo profesionales pueden aprobar planes.")

    try:
        plan = AIPlanService.approve_plan(db=db, plan_id=plan_id, nutritionist_id=current_user.id)
        return plan
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/patient/{patient_id}", response_model=List[NutritionalPlanResponse])
def get_patient_plans(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consulta la lista de planes (borradores y aprobados) de un paciente."""
    if current_user.role_id in ["CLIENTE", "PACIENTE"] and current_user.id != patient_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    plans = (
        db.query(NutritionalPlan)
        .filter(NutritionalPlan.patient_id == patient_id)
        .order_by(NutritionalPlan.created_at.desc())
        .all()
    )
    return [AIPlanService._format_plan_response(p) for p in plans]


@router.get("/my-plan", response_model=Optional[NutritionalPlanResponse])
def get_my_active_plan(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El paciente consulta su plan aprobado vigente (o borrador en caso de no tener aprobado aún)."""
    plan = (
        db.query(NutritionalPlan)
        .filter(NutritionalPlan.patient_id == current_user.id, NutritionalPlan.status == "APPROVED")
        .order_by(NutritionalPlan.approved_at.desc())
        .first()
    )

    if not plan:
        plan = (
            db.query(NutritionalPlan)
            .filter(NutritionalPlan.patient_id == current_user.id)
            .order_by(NutritionalPlan.created_at.desc())
            .first()
        )

    if not plan:
        return None

    return AIPlanService._format_plan_response(plan)
