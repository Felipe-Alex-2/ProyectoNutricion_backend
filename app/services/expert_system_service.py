import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.clinical import PatientAnamnesis
from app.models.ai_nutrition import (
    ConditionCatalog,
    ExclusionRule,
    HabitParameter,
    Food,
    FoodTag,
)
from app.schemas.ai_nutrition import HabitEvaluationItem, HabitEvaluationResult

logger = logging.getLogger(__name__)


class ExpertSystemService:
    """Motor del Sistema Experto: reglas determinísticas, cálculo metabólico y exclusión de alimentos."""

    @staticmethod
    def calculate_calories_and_macros(
        anamnesis: PatientAnamnesis,
        custom_goal: Optional[str] = None,
        custom_adjustment_pct: Optional[float] = None,
        custom_meals_per_day: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Calcula TMB con la fórmula Mifflin-St Jeor, aplica factor de actividad y ajusta según objetivo clínico.
        Límites de seguridad: >= 1200 kcal (mujer) / >= 1500 kcal (hombre).
        """
        weight = float(anamnesis.weight_kg or 70.0)
        height = float(anamnesis.height_cm or 170.0)
        gender = (anamnesis.gender or "M").upper()

        # Calcular edad desde fecha de nacimiento (default: 30 años)
        age = 30
        if anamnesis.birth_date:
            now = datetime.now(timezone.utc)
            bdate = anamnesis.birth_date
            if bdate.tzinfo is None:
                bdate = bdate.replace(tzinfo=timezone.utc)
            age = max(15, min(100, int((now - bdate).days / 365.25)))

        # 1. Tasa Metabólica Basal (Mifflin-St Jeor)
        # Hombre: 10·peso + 6.25·talla − 5·edad + 5
        # Mujer:  10·peso + 6.25·talla − 5·edad − 161
        if gender == "F":
            tmb = (10.0 * weight) + (6.25 * height) - (5.0 * age) - 161.0
        else:
            tmb = (10.0 * weight) + (6.25 * height) - (5.0 * age) + 5.0

        tmb = max(900.0, tmb)

        # 2. Factor de Actividad Física
        act = (anamnesis.physical_activity or "Ligero").lower()
        if "sedent" in act:
            activity_multiplier = 1.2
        elif "moder" in act:
            activity_multiplier = 1.55
        elif "intens" in act or "fuerte" in act:
            activity_multiplier = 1.725
        else:
            activity_multiplier = 1.375  # Ligero por defecto

        get_total = tmb * activity_multiplier

        # 3. Ajuste según Objetivo
        goal_text = (custom_goal or anamnesis.goal or "Pérdida de grasa").lower()
        adjustment_pct = 0.0

        if custom_adjustment_pct is not None:
            adjustment_pct = custom_adjustment_pct
        elif "pérdida" in goal_text or "grasa" in goal_text or "deficit" in goal_text:
            adjustment_pct = -18.0  # -15% a -20%
        elif "masa" in goal_text or "volumen" in goal_text or "muscular" in goal_text:
            adjustment_pct = +10.0
        else:
            adjustment_pct = 0.0  # Mantenimiento / salud

        target_calories = get_total * (1.0 + (adjustment_pct / 100.0))

        # 4. Límites de seguridad clínica
        requires_special_review = False
        warnings = []

        min_safe = 1200.0 if gender == "F" else 1500.0
        if target_calories < min_safe:
            target_calories = min_safe
            requires_special_review = True
            warnings.append(f"Calorías ajustadas al umbral mínimo de seguridad ({min_safe} kcal).")

        if anamnesis.is_pregnant_or_lactating:
            requires_special_review = True
            warnings.append("Paciente en estado de embarazo/lactancia: requiere prescripción directa del especialista.")

        # 5. Distribución de Macronutrientes
        # Proteína: 1.8 g/kg (entre 1.6 y 2.0 g/kg)
        protein_g = round(weight * 1.8, 1)
        protein_kcal = protein_g * 4.0

        # Grasas: 25% del total calórico (9 kcal/g)
        fats_kcal = target_calories * 0.25
        fats_g = round(fats_kcal / 9.0, 1)

        # Carbohidratos: restante calórico (4 kcal/g)
        carbs_kcal = max(0.0, target_calories - protein_kcal - fats_kcal)
        carbs_g = round(carbs_kcal / 4.0, 1)

        meals_per_day = custom_meals_per_day or anamnesis.meals_per_day or 4

        return {
            "tmb": round(tmb, 1),
            "activity_multiplier": activity_multiplier,
            "get_total": round(get_total, 1),
            "adjustment_pct": adjustment_pct,
            "target_calories": round(target_calories, 1),
            "protein_g": protein_g,
            "fats_g": fats_g,
            "carbs_g": carbs_g,
            "meals_per_day": meals_per_day,
            "requires_special_review": requires_special_review,
            "warnings": warnings,
            "calculated_age": age,
        }

    @staticmethod
    def filter_foods_for_patient(
        db: Session,
        anamnesis: Optional[PatientAnamnesis],
        food_list: List[Dict[str, Any]],
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Aplica las reglas de exclusión del sistema experto:
        Filtra alimentos cuya etiqueta esté contraindicada según las condiciones del paciente.
        """
        if not anamnesis:
            return food_list, []

        # Recolectar condiciones clínicas (patologías, alergias y texto libre)
        patient_conditions = []
        if anamnesis.allergies:
            patient_conditions.extend([c.strip().upper() for c in anamnesis.allergies.replace(";", ",").split(",") if c.strip()])
        if anamnesis.pathologies:
            patient_conditions.extend([c.strip().upper() for c in anamnesis.pathologies.replace(";", ",").split(",") if c.strip()])
        if anamnesis.other_allergies:
            patient_conditions.extend([c.strip().upper() for c in anamnesis.other_allergies.replace(";", ",").split(",") if c.strip()])

        # Buscar reglas en la base de datos
        db_rules = db.query(ExclusionRule).all()
        excluded_tags = set()

        for cond in patient_conditions:
            for rule in db_rules:
                if rule.condition_code.upper() in cond or cond in rule.condition_code.upper():
                    excluded_tags.add(rule.excluded_tag.upper())

        # Mapeos directos de contingencia si no hay reglas cargadas aún
        combined_text = f"{anamnesis.allergies or ''} {anamnesis.pathologies or ''} {anamnesis.other_allergies or ''}".lower()
        if "lactosa" in combined_text or "leche" in combined_text:
            excluded_tags.add("LACTOSA")
        if "gluten" in combined_text or "celiac" in combined_text or "trigo" in combined_text:
            excluded_tags.add("GLUTEN")
        if "diabet" in combined_text or "resistencia a la insulina" in combined_text:
            excluded_tags.add("AZUCAR_ALTO")
        if "hipertens" in combined_text or "presion" in combined_text:
            excluded_tags.add("SODIO_ALTO")

        filtered = []
        applied_exclusions = []

        for item in food_list:
            name = (item.get("nombre") or item.get("name") or "").lower()
            prohibited = False

            if "LACTOSA" in excluded_tags and any(w in name for w in ["leche entera", "queso crema", "crema de leche", "mantequilla"]):
                prohibited = True
                applied_exclusions.append(f"Excluido '{item.get('name') or item.get('nombre')}' por condición de intolerancia a lactosa.")
            elif "GLUTEN" in excluded_tags and any(w in name for w in ["trigo", "pan blanco", "galleta común", "harina"]):
                prohibited = True
                applied_exclusions.append(f"Excluido '{item.get('name') or item.get('nombre')}' por condición de intolerancia a gluten.")
            elif "AZUCAR_ALTO" in excluded_tags and any(w in name for w in ["azúcar", "gaseosa", "dulce", "almíbar", "caramelo"]):
                prohibited = True
                applied_exclusions.append(f"Excluido '{item.get('name') or item.get('nombre')}' por condición de diabetes/resistencia insulínica.")
            elif "SODIO_ALTO" in excluded_tags and any(w in name for w in ["embutido", "salchicha", "conserva", "enlatado con sal"]):
                prohibited = True
                applied_exclusions.append(f"Excluido '{item.get('name') or item.get('nombre')}' por control de hipertensión.")

            if not prohibited:
                filtered.append(item)

        return filtered, applied_exclusions

    @staticmethod
    def evaluate_weekly_habits(
        db: Session,
        anamnesis: PatientAnamnesis,
        patient_name: str,
        water_override: Optional[float] = None,
        fruits_override: Optional[int] = None,
        sugary_override: Optional[int] = None,
        sleep_override: Optional[float] = None,
    ) -> HabitEvaluationResult:
        """
        Evalúa el cumplimiento de hábitos saludables según los parámetros de la BD:
        AGUA >= 2.0 L, FRUTAS >= 3, BEBIDAS_AZUCARADAS <= 3, SUENO >= 7.0 h.
        """
        # Obtener parámetros configurados o usar valores por defecto clínicos
        params = db.query(HabitParameter).all()
        param_map = {p.habit: (p.operator, p.value, p.unit) for p in params}

        default_rules = {
            "AGUA": (">=", 2.0, "L"),
            "FRUTAS": (">=", 3.0, "porciones"),
            "BEBIDAS_AZUCARADAS": ("<=", 3.0, "vasos"),
            "SUENO": (">=", 7.0, "horas"),
        }

        water_val = water_override if water_override is not None else float(anamnesis.water_intake_liters or 1.5)
        fruits_val = fruits_override if fruits_override is not None else float(anamnesis.fruits_vegetables_daily or 3)
        sugary_val = sugary_override if sugary_override is not None else float(anamnesis.sugary_drinks_weekly or 0)
        sleep_val = sleep_override if sleep_override is not None else float(anamnesis.sleep_hours or 7.0)

        checks = [
            ("AGUA", water_val, "L"),
            ("FRUTAS", fruits_val, "porciones"),
            ("BEBIDAS_AZUCARADAS", sugary_val, "vasos"),
            ("SUENO", sleep_val, "horas"),
        ]

        items: List[HabitEvaluationItem] = []
        unfulfilled = 0

        for habit_name, current_val, fallback_unit in checks:
            rule = param_map.get(habit_name, default_rules.get(habit_name, (">=", 1.0, fallback_unit)))
            op, required_val, unit = rule

            if op == ">=":
                fulfilled = current_val >= required_val
            elif op == "<=":
                fulfilled = current_val <= required_val
            else:
                fulfilled = True

            if not fulfilled:
                unfulfilled += 1
                feedback = f"Requiere ajuste: registro {current_val} {unit}, meta recomendada {op} {required_val} {unit}."
            else:
                feedback = f"Excelente: {current_val} {unit} dentro del rango óptimo ({op} {required_val} {unit})."

            items.append(
                HabitEvaluationItem(
                    habit=habit_name,
                    current_value=current_val,
                    required_value=required_val,
                    operator=op,
                    unit=unit,
                    fulfilled=fulfilled,
                    feedback=feedback,
                )
            )

        status_str = "HABITOS_POR_MEJORAR" if unfulfilled >= 2 else "TODO_BIEN"

        if status_str == "TODO_BIEN":
            msg = f"¡Felicitaciones {patient_name}! Has cumplido tus metas de hidratación, descanso y hábitos saludables esta semana."
        else:
            msg = f"Hola {patient_name}, tu seguimiento semanal detectó {unfulfilled} hábito(s) por mejorar. Revisa las recomendaciones en tu app."

        return HabitEvaluationResult(
            patient_id=anamnesis.patient_id,
            patient_name=patient_name,
            evaluation_status=status_str,
            total_evaluated=len(items),
            unfulfilled_count=unfulfilled,
            items=items,
            notification_message=msg,
            evaluated_at=datetime.now(timezone.utc),
        )

    @classmethod
    def seed_default_expert_data(cls, db: Session) -> None:
        """Inicializa los catálogos y reglas del sistema experto si aún no existen."""
        # 1. Catálogo de Condiciones
        if db.query(ConditionCatalog).count() == 0:
            default_conditions = [
                ("LACTOSA", "ALERGIA", "Intolerancia a la Lactosa", "Incapacidad para digerir azúcares lácteos"),
                ("GLUTEN", "ALERGIA", "Intolerancia al Gluten / Celíaco", "Sensibilidad o patología celíaca"),
                ("FRUTOS_SECOS", "ALERGIA", "Alergia a Frutos Secos", "Reacción adversa a maní, nueces, almendras"),
                ("MARISCOS", "ALERGIA", "Alergia a Mariscos", "Reacción adversa a pescados o mariscos"),
                ("DIABETES", "ANTECEDENTE", "Diabetes Mellitus Tipo 2", "Alteración en la regulación glucémica"),
                ("HIPERTENSION", "ANTECEDENTE", "Hipertensión Arterial", "Presión sanguínea crónicamente elevada"),
                ("DISLIPIDEMIA", "ANTECEDENTE", "Dislipidemia / Colesterol", "Niveles elevados de colesterol o triglicéridos"),
            ]
            for code, ctype, name, desc in default_conditions:
                db.add(ConditionCatalog(code=code, type=ctype, name=name, description=desc))

        # 2. Reglas de Exclusión
        if db.query(ExclusionRule).count() == 0:
            default_rules = [
                ("LACTOSA", "LACTOSA", "Excluir alimentos con lactosa sin sustitución"),
                ("GLUTEN", "GLUTEN", "Excluir cereales con gluten para celíacos"),
                ("DIABETES", "AZUCAR_ALTO", "Restringir azúcares refinados y alta carga glucémica"),
                ("HIPERTENSION", "SODIO_ALTO", "Restringir alimentos ultraprocesados ricos en sodio"),
            ]
            for cond, tag, reason in default_rules:
                db.add(ExclusionRule(condition_code=cond, excluded_tag=tag, reason=reason))

        # 3. Parámetros de Hábitos
        if db.query(HabitParameter).count() == 0:
            default_habits = [
                ("AGUA", ">=", 2.0, "L", "Consumo mínimo saludable de agua diaria"),
                ("FRUTAS", ">=", 3.0, "porciones", "Porciones mínimas de frutas y verduras frescas al día"),
                ("BEBIDAS_AZUCARADAS", "<=", 3.0, "vasos", "Límite máximo recomendado de refrescos azucarados semanales"),
                ("SUENO", ">=", 7.0, "horas", "Descanso mínimo reparador por noche"),
            ]
            for habit, op, val, unit, desc in default_habits:
                db.add(HabitParameter(habit=habit, operator=op, value=val, unit=unit, description=desc))

        db.commit()
