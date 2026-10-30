import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.clinical import PatientAnamnesis
from app.models.patient_link import PatientNutritionistLink
from app.models.ai_nutrition import NutritionalPlan
from app.models.notification import Notification
from app.services.gemini_service import GeminiService
from app.services.expert_system_service import ExpertSystemService
from app.schemas.ai_nutrition import (
    NutritionalPlanResponse,
    MealItem,
    FoodItem,
    WeeklyMenuResponse,
    DayMenu,
)

logger = logging.getLogger(__name__)


class AIPlanService:
    """Servicio de generación, ajuste y aprobación de planes nutricionales y menú semanal."""

    @classmethod
    def generate_plan_draft(
        cls,
        db: Session,
        patient_id: str,
        nutritionist_id: Optional[str] = None,
        custom_goal: Optional[str] = None,
        calorie_adjustment_pct: Optional[float] = None,
        meals_per_day: Optional[int] = 4,
    ) -> NutritionalPlanResponse:
        """
        Calcula TMB/macros determinísticamente, consulta a Gemini (o template clínico),
        filtra exclusiones con el sistema experto y almacena el borrador para revisión del especialista.
        """
        patient = db.query(User).filter(User.id == patient_id).first()
        if not patient:
            raise ValueError("Paciente no encontrado.")

        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        if not anamnesis:
            raise ValueError("El paciente aún no ha completado su anamnesis de salud inicial.")

        # 1. Cálculo determinístico (Mifflin-St Jeor + factor de actividad + macros)
        calc = ExpertSystemService.calculate_calories_and_macros(
            anamnesis=anamnesis,
            custom_goal=custom_goal,
            custom_adjustment_pct=calorie_adjustment_pct,
            custom_meals_per_day=meals_per_day,
        )

        daily_kcal = calc["target_calories"]
        protein_g = calc["protein_g"]
        carbs_g = calc["carbs_g"]
        fats_g = calc["fats_g"]
        num_meals = calc["meals_per_day"]

        # 2. Construcción de comidas (Gemini LLM o Template Clínico Estructurado)
        meals = cls._generate_meals_structure(
            anamnesis=anamnesis,
            daily_kcal=daily_kcal,
            protein_g=protein_g,
            carbs_g=carbs_g,
            fats_g=fats_g,
            meals_count=num_meals,
            goal=custom_goal,
        )

        # 3. Aplicar Filtro de Exclusión del Sistema Experto
        for meal in meals:
            filtered_foods, exclusions = ExpertSystemService.filter_foods_for_patient(
                db=db,
                anamnesis=anamnesis,
                food_list=[f.model_dump() for f in meal.foods],
            )
            meal.foods = [FoodItem(**f) for f in filtered_foods]
            meal.total_calories = round(sum(f.calories for f in meal.foods), 1)
            if not meal.foods or meal.total_calories <= 0:
                raise ValueError('El menú propuesto no cumple las restricciones del paciente. Ajusta la solicitud y vuelve a generar el borrador.')

        proposed_calories = sum(m.total_calories for m in meals)
        if abs(proposed_calories - daily_kcal) > daily_kcal * .15:
            calc['requires_special_review'] = True
            calc['warnings'].append('Las calorías de las comidas difieren del objetivo. Revisar porciones antes de aprobar.')

        # 4. Persistir o actualizar plan en estado DRAFT
        existing_draft = (
            db.query(NutritionalPlan)
            .filter(NutritionalPlan.patient_id == patient_id, NutritionalPlan.status == "DRAFT")
            .first()
        )

        plan_data = {
            "title": f"Plan Nutricional - {custom_goal or anamnesis.goal}",
            "goal": custom_goal or anamnesis.goal,
            "daily_calories": daily_kcal,
            "protein_g": protein_g,
            "carbs_g": carbs_g,
            "fats_g": fats_g,
            "meals_per_day": num_meals,
            "meals_json": json.dumps([m.model_dump() for m in meals], ensure_ascii=False),
            "requires_special_review": calc["requires_special_review"],
            "clinical_notes": (
                "Menú propuesto por Gemini IA. Requiere revisión profesional. "
                f"TMB calculada: {calc['tmb']} kcal (Mifflin-St Jeor). "
                f"Ajuste metabólico: {calc['adjustment_pct']}%. "
                + (" ".join(calc["warnings"]) if calc["warnings"] else "")
            ),
        }

        if existing_draft:
            for k, v in plan_data.items():
                setattr(existing_draft, k, v)
            existing_draft.nutritionist_id = nutritionist_id or existing_draft.nutritionist_id
            plan = existing_draft
        else:
            plan = NutritionalPlan(
                patient_id=patient_id,
                nutritionist_id=nutritionist_id,
                tenant_id=patient.tenant_id,
                status="DRAFT",
                **plan_data,
            )
            db.add(plan)

        db.commit()
        db.refresh(plan)

        return cls._format_plan_response(plan)

    @classmethod
    def update_plan(
        cls,
        db: Session,
        plan_id: str,
        title: Optional[str] = None,
        daily_calories: Optional[float] = None,
        protein_g: Optional[float] = None,
        carbs_g: Optional[float] = None,
        fats_g: Optional[float] = None,
        meals: Optional[List[MealItem]] = None,
        clinical_notes: Optional[str] = None,
        status: Optional[str] = None,
        approved_by: Optional[str] = None,
    ) -> NutritionalPlanResponse:
        """Actualiza valores o comidas de un plan existente (por nutricionista)."""
        plan = db.query(NutritionalPlan).filter(NutritionalPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Plan nutricional no encontrado.")

        if title is not None:
            plan.title = title
        if daily_calories is not None:
            plan.daily_calories = daily_calories
        if protein_g is not None:
            plan.protein_g = protein_g
        if carbs_g is not None:
            plan.carbs_g = carbs_g
        if fats_g is not None:
            plan.fats_g = fats_g
        if meals is not None:
            plan.meals_json = json.dumps([m.model_dump() for m in meals], ensure_ascii=False)
            plan.meals_per_day = len(meals)
        if clinical_notes is not None:
            plan.clinical_notes = clinical_notes
        if status is not None:
            if status == "APPROVED":
                return cls.approve_plan(db, plan_id, approved_by or plan.nutritionist_id)
            plan.status = status

        db.commit()
        db.refresh(plan)
        return cls._format_plan_response(plan)

    @classmethod
    def approve_plan(
        cls,
        db: Session,
        plan_id: str,
        nutritionist_id: str,
    ) -> NutritionalPlanResponse:
        """Aprueba un borrador y archiva planes anteriores activos."""
        plan = db.query(NutritionalPlan).filter(NutritionalPlan.id == plan_id).first()
        if not plan:
            raise ValueError("Plan nutricional no encontrado.")

        # Serialize assignment per patient so concurrent approvals cannot leave two active plans.
        db.query(User).filter(User.id == plan.patient_id).with_for_update().one()
        db.flush()
        db.refresh(plan)
        if plan.status == 'APPROVED':
            db.commit()
            return cls._format_plan_response(plan)
        if not nutritionist_id:
            raise ValueError('La aprobación requiere un profesional responsable.')
        if not json.loads(plan.meals_json or '[]'):
            raise ValueError('El plan debe incluir comidas antes de asignarlo.')
        for previous in db.query(NutritionalPlan).filter(
            NutritionalPlan.patient_id == plan.patient_id,
            NutritionalPlan.id != plan_id,
            NutritionalPlan.status == "APPROVED",
        ).all():
            previous.status = "ARCHIVED"

        plan.status = "APPROVED"
        plan.nutritionist_id = nutritionist_id
        plan.approved_at = datetime.now(timezone.utc)
        db.add(Notification(user_id=plan.patient_id, tenant_id=plan.tenant_id,
            title='Tu plan nutricional está listo',
            message='Tu profesional aprobó y asignó tu plan. Consúltalo en Mi plan o Mi nutrición.',
            type='SISTEMA', reference_id=plan.id, is_read=False))
        db.commit()
        db.refresh(plan)

        return cls._format_plan_response(plan)

    @classmethod
    def generate_weekly_menu(
        cls,
        db: Session,
        patient_id: str,
        special_instructions: Optional[str] = None,
    ) -> WeeklyMenuResponse:
        """
        Genera el menú de 7 días.
        REGLA CLÍNICA OBLIGATORIA: El paciente debe estar vinculado a un nutricionista
        y contar con un plan nutricional aprobado.
        """
        # 1. Validar vinculación activa con nutricionista
        link = (
            db.query(PatientNutritionistLink)
            .filter(
                PatientNutritionistLink.patient_id == patient_id,
                PatientNutritionistLink.status == "LINKED",
            )
            .first()
        )
        if not link or not link.nutritionist_id:
            raise PermissionError(
                "Función bloqueada: Debes vincularte con tu especialista nutricional para acceder al Menú Semanal."
            )

        # 2. Validar plan aprobado
        approved_plan = (
            db.query(NutritionalPlan)
            .filter(
                NutritionalPlan.patient_id == patient_id,
                NutritionalPlan.status == "APPROVED",
            )
            .order_by(NutritionalPlan.approved_at.desc())
            .first()
        )
        if not approved_plan:
            raise PermissionError(
                "Aún no cuentas con un plan nutricional aprobado por tu nutricionista. Solicita la aprobación en tu consulta."
            )

        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        base_meals = []
        try:
            base_meals_data = json.loads(approved_plan.meals_json)
            base_meals = [MealItem(**m) for m in base_meals_data]
        except Exception:
            base_meals = []

        # Generar variaciones de 7 días
        days_names = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        day_menus: List[DayMenu] = []

        for idx, day_name in enumerate(days_names):
            day_meals = []
            for m in base_meals:
                varied_foods = []
                for f in m.foods:
                    # Pequeña variación de ingredientes manteniendo macronutrientes
                    food_name = f.name
                    if idx % 2 == 1 and "pollo" in food_name.lower():
                        food_name = food_name.replace("Pollo", "Pavo").replace("pollo", "pavo")
                    elif idx % 2 == 1 and "arroz" in food_name.lower():
                        food_name = food_name.replace("Arroz", "Quinoa").replace("arroz", "quinoa")

                    varied_foods.append(
                        FoodItem(
                            name=food_name,
                            portion=f.portion,
                            calories=f.calories,
                            protein_g=f.protein_g,
                            carbs_g=f.carbs_g,
                            fats_g=f.fats_g,
                        )
                    )

                # Filtrar exclusiones
                filtered_foods, _ = ExpertSystemService.filter_foods_for_patient(
                    db=db,
                    anamnesis=anamnesis,
                    food_list=[vf.model_dump() for vf in varied_foods],
                )
                final_foods = [FoodItem(**ff) for ff in filtered_foods]
                day_meals.append(
                    MealItem(
                        meal_name=m.meal_name,
                        time_suggestion=m.time_suggestion,
                        foods=final_foods,
                        total_calories=round(sum(ff.calories for ff in final_foods), 1),
                    )
                )

            day_menus.append(
                DayMenu(
                    day=day_name,
                    meals=day_meals,
                    daily_calories=round(sum(dm.total_calories for dm in day_meals), 1),
                )
            )

        # Guardar copia del menú en el plan
        approved_plan.weekly_menu_json = json.dumps([dm.model_dump() for dm in day_menus], ensure_ascii=False)
        db.commit()

        return WeeklyMenuResponse(
            patient_id=patient_id,
            nutritionist_id=link.nutritionist_id,
            plan_id=approved_plan.id,
            days=day_menus,
            excluded_allergens=[c.strip() for c in (anamnesis.allergies or "").split(",") if c.strip()] if anamnesis else [],
            generated_at=datetime.now(timezone.utc),
        )

    @classmethod
    def _generate_meals_structure(
        cls,
        anamnesis: PatientAnamnesis,
        daily_kcal: float,
        protein_g: float,
        carbs_g: float,
        fats_g: float,
        meals_count: int,
        goal: Optional[str] = None,
    ) -> List[MealItem]:
        """Generate a structured AI draft; failures must never masquerade as AI output."""
        if not GeminiService.is_configured():
            raise ValueError("Configura GEMINI_API_KEY en el servicio backend para generar planes con IA.")
        prompt = (
            f"Genera un plan de alimentación diario para un paciente con meta '{goal or anamnesis.goal}'. "
            f"Calorías totales: {daily_kcal} kcal, Proteína: {protein_g}g, Carbohidratos: {carbs_g}g, Grasas: {fats_g}g. "
            f"Número de comidas: {meals_count}. "
            f"Alergias del paciente: {anamnesis.allergies or 'Ninguna'}. "
            f"Condiciones clínicas: {anamnesis.pathologies or 'Sin información'}. "
            f"Preferencias: {anamnesis.food_preferences or 'Sin restricciones'}. "
            f'Devuelve un objeto JSON con la clave "meals" y esta lista:\n'
            "[\n"
            "  {\n"
            '    "meal_name": "Desayuno",\n'
            '    "time_suggestion": "08:00",\n'
            '    "foods": [\n'
            '      {"name": "Huevos revueltos", "portion": "2 unidades", "calories": 140, "protein_g": 12, "carbs_g": 1, "fats_g": 10}\n'
            "    ],\n"
            '    "total_calories": 140\n'
            "  }\n"
            "]"
        )
        raw_json = GeminiService.generate_json(prompt)
        if isinstance(raw_json, dict):
            raw_json = raw_json.get("meals", [])
        if isinstance(raw_json, list) and len(raw_json) == meals_count:
            try:
                meals = [MealItem(**item) for item in raw_json]
                if all(meal.foods for meal in meals):
                    return meals
            except (ValueError, TypeError):
                logger.warning('La IA devolvió comidas con una estructura inválida.')

        raise ValueError("La IA no devolvió un menú válido. Intenta nuevamente; no se ha guardado un plan generado.")

    @classmethod
    def _format_plan_response(cls, plan: NutritionalPlan) -> NutritionalPlanResponse:
        meals = []
        try:
            meals_data = json.loads(plan.meals_json) if plan.meals_json else []
            meals = [MealItem(**m) for m in meals_data]
        except Exception:
            meals = []

        weekly = None
        if plan.weekly_menu_json:
            try:
                weekly = json.loads(plan.weekly_menu_json)
            except Exception:
                weekly = None

        return NutritionalPlanResponse(
            id=plan.id,
            patient_id=plan.patient_id,
            nutritionist_id=plan.nutritionist_id,
            tenant_id=plan.tenant_id,
            status=plan.status,
            title=plan.title,
            goal=plan.goal,
            daily_calories=plan.daily_calories,
            protein_g=plan.protein_g,
            carbs_g=plan.carbs_g,
            fats_g=plan.fats_g,
            meals_per_day=plan.meals_per_day,
            meals=meals,
            weekly_menu=weekly,
            clinical_notes=plan.clinical_notes,
            requires_special_review=plan.requires_special_review,
            approved_at=plan.approved_at,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
