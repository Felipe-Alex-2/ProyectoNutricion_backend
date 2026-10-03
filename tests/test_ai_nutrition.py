import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.models.user import User
from app.models.clinical import PatientAnamnesis
from app.models.patient_link import PatientNutritionistLink
from app.models.ai_nutrition import NutritionalPlan, ExclusionRule, HabitParameter
from app.services.expert_system_service import ExpertSystemService
from app.services.ai_plan_service import AIPlanService
from app.services.chat_service import ChatService
from app.services.food_vision_service import FoodVisionService
from app.services.automation_service import AutomationService


def test_expert_system_calculations(db_session):
    """Prueba de cálculo determinístico Mifflin-St Jeor y macronutrientes."""
    anamnesis = PatientAnamnesis(
        patient_id="test-patient-id",
        gender="M",
        weight_kg=80.0,
        height_cm=180.0,
        physical_activity="Moderado",
        goal="Pérdida de grasa",
        birth_date=datetime(1995, 5, 20, tzinfo=timezone.utc),
    )

    calc = ExpertSystemService.calculate_calories_and_macros(anamnesis)

    # TMB Mifflin-St Jeor Hombre: 10*80 + 6.25*180 - 5*edad + 5
    assert calc["tmb"] > 1600.0
    assert calc["activity_multiplier"] == 1.55
    assert calc["adjustment_pct"] == -18.0
    assert calc["protein_g"] == round(80.0 * 1.8, 1)
    assert calc["target_calories"] >= 1500.0


def test_safety_limits_female(db_session):
    """Verifica límite de seguridad calórico para mujer (mínimo 1200 kcal)."""
    anamnesis = PatientAnamnesis(
        patient_id="female-id",
        gender="F",
        weight_kg=40.0,
        height_cm=145.0,
        physical_activity="Sedentario",
        goal="Pérdida de grasa",
        birth_date=datetime(1990, 1, 1, tzinfo=timezone.utc),
    )
    calc = ExpertSystemService.calculate_calories_and_macros(anamnesis, custom_adjustment_pct=-30.0)
    assert calc["target_calories"] == 1200.0
    assert calc["requires_special_review"] is True


def test_food_exclusion_filter(db_session):
    """Verifica exclusión de alérgenos y contraindicaciones."""
    anamnesis = PatientAnamnesis(
        patient_id="p-allergy",
        allergies="Lactosa, Gluten",
        pathologies="Diabetes",
    )
    foods = [
        {"name": "Pechuga de pollo al horno", "calories": 200},
        {"name": "Leche entera fresca", "calories": 150},
        {"name": "Pan blanco de trigo", "calories": 120},
        {"name": "Bebida dulce azucarada", "calories": 180},
    ]

    filtered, exclusions = ExpertSystemService.filter_foods_for_patient(db_session, anamnesis, foods)
    names = [f["name"] for f in filtered]

    assert "Pechuga de pollo al horno" in names
    assert "Leche entera fresca" not in names
    assert "Pan blanco de trigo" not in names
    assert "Bebida dulce azucarada" not in names
    assert len(exclusions) == 3


def test_habit_evaluation(db_session):
    """Verifica evaluación de hábitos saludables semanales."""
    ExpertSystemService.seed_default_expert_data(db_session)
    anamnesis = PatientAnamnesis(
        patient_id="p-habits",
        water_intake_liters=1.0,  # Falla (esperado >= 2.0)
        fruits_vegetables_daily=1,  # Falla (esperado >= 3)
        sugary_drinks_weekly=5,  # Falla (esperado <= 3)
        sleep_hours=6.0,  # Falla (esperado >= 7)
    )

    res = ExpertSystemService.evaluate_weekly_habits(db_session, anamnesis, "Juan Perez")
    assert res.evaluation_status == "HABITOS_POR_MEJORAR"
    assert res.unfulfilled_count >= 3


def test_chat_emergency_keyword(db_session):
    """Verifica que el chatbot Carlitos deriva inmediatamente ante síntomas de riesgo."""
    user = User(
        id="user-chat",
        email="chat@nutri.com",
        hashed_password="hash",
        full_name="Carlos Gomez",
    )
    db_session.add(user)
    db_session.commit()

    reply = ChatService.process_message(db_session, user.id, "Ayer tuve un desmayo y me mareo mucho")
    assert "médica importante" in reply.content
    assert "urgencias" in reply.content


def test_weekly_menu_requires_linked_nutritionist(db_session):
    """Verifica que el menú semanal exige estar vinculado con un nutricionista."""
    patient = User(
        id="unlinked-patient",
        email="unlinked@nutri.com",
        hashed_password="hash",
        full_name="Paciente No Vinculado",
    )
    db_session.add(patient)
    db_session.commit()

    with pytest.raises(PermissionError) as exc_info:
        AIPlanService.generate_weekly_menu(db_session, patient.id)
    assert "vincularte" in str(exc_info.value).lower()
