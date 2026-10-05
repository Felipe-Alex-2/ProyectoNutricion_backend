from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# =====================================================================
# 1. PLAN NUTRICIONAL & MENÚ SEMANAL
# =====================================================================

class FoodItem(BaseModel):
    name: str
    portion: str
    calories: float = 0.0
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fats_g: float = 0.0


class MealItem(BaseModel):
    meal_name: str  # Desayuno, Almuerzo, Merienda, Cena, Snack
    time_suggestion: Optional[str] = None
    foods: List[FoodItem] = []
    total_calories: float = 0.0


class NutritionalPlanCreate(BaseModel):
    patient_id: str
    title: Optional[str] = "Plan Nutricional Personalizado"
    goal: Optional[str] = "Pérdida de grasa"
    daily_calories: float = 2000.0
    protein_g: float = 120.0
    carbs_g: float = 220.0
    fats_g: float = 60.0
    meals_per_day: int = 4
    meals: List[MealItem] = []
    clinical_notes: Optional[str] = None
    requires_special_review: bool = False


class NutritionalPlanUpdate(BaseModel):
    title: Optional[str] = None
    daily_calories: Optional[float] = None
    protein_g: Optional[float] = None
    carbs_g: Optional[float] = None
    fats_g: Optional[float] = None
    meals_per_day: Optional[int] = None
    meals: Optional[List[MealItem]] = None
    clinical_notes: Optional[str] = None
    status: Optional[str] = None  # DRAFT, APPROVED, REJECTED


class PlanGenerateRequest(BaseModel):
    patient_id: str
    custom_goal: Optional[str] = None
    calorie_adjustment_pct: Optional[float] = None  # e.g. -15.0 or 10.0
    meals_per_day: Optional[int] = 4
    include_ai_reasoning: bool = True


class NutritionalPlanResponse(BaseModel):
    id: str
    patient_id: str
    nutritionist_id: Optional[str] = None
    tenant_id: Optional[str] = None
    status: str
    title: str
    goal: str
    daily_calories: float
    protein_g: float
    carbs_g: float
    fats_g: float
    meals_per_day: int
    meals: List[MealItem] = []
    weekly_menu: Optional[Dict[str, Any]] = None
    clinical_notes: Optional[str] = None
    requires_special_review: bool
    approved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WeeklyMenuGenerateRequest(BaseModel):
    patient_id: str
    special_instructions: Optional[str] = None


class DayMenu(BaseModel):
    day: str  # Lunes, Martes, etc.
    meals: List[MealItem]
    daily_calories: float


class WeeklyMenuResponse(BaseModel):
    patient_id: str
    nutritionist_id: Optional[str]
    plan_id: str
    days: List[DayMenu]
    excluded_allergens: List[str] = []
    generated_at: datetime


# =====================================================================
# 2. CHATBOT CARLITOS
# =====================================================================

class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1000, description="Pregunta del paciente a Carlitos")


class ChatMessageResponse(BaseModel):
    id: str
    patient_id: str
    role: str  # user, assistant
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatHistoryResponse(BaseModel):
    patient_id: str
    patient_goal: Optional[str] = None
    messages: List[ChatMessageResponse] = []


# =====================================================================
# 3. VISIÓN POR COMPUTADORA (FOTO DE COMIDA)
# =====================================================================

class DetectedFood(BaseModel):
    nombre: str
    porcion_aprox_g: float = 0.0
    carbohidratos_g: float = 0.0
    calorias: float = 0.0
    proteinas_g: float = 0.0
    grasas_g: float = 0.0
    fibra_g: float = 0.0


class FoodAnalysisTotals(BaseModel):
    calorias: float = 0.0
    carbohidratos_g: float = 0.0
    proteinas_g: float = 0.0
    grasas_g: float = 0.0
    fibra_g: float = 0.0


class FoodAnalysisEvaluation(BaseModel):
    status: str  # OPTIMO, EXCESO_CARBOHIDRATOS, DEFICIT_PROTEINA, etc.
    daily_target_calories: float = 0.0
    meal_recommended_calories: float = 0.0
    comparison_message: str
    disclaimer: str = "Estimación aproximada de apoyo visual. No sustituye la consulta médica/nutricional."


class FoodAnalysisResponse(BaseModel):
    record_id: Optional[str] = None
    alimentos: List[DetectedFood] = []
    total: FoodAnalysisTotals
    confianza: str = "media"  # alta, media, baja
    observaciones: str = ""
    evaluacion: Optional[FoodAnalysisEvaluation] = None
    image_url: Optional[str] = None
    created_at: datetime


class FoodRecordResponse(BaseModel):
    id: str
    patient_id: str
    image_url: Optional[str] = None
    estimated_calories: float
    estimated_carbs: float
    estimated_protein: float
    estimated_fats: float
    estimated_fiber: float = 0.0
    confidence: str
    notes: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    created_at: datetime

    class Config:
        from_attributes = True


# =====================================================================
# 4. SISTEMA EXPERTO, CONDICIONES Y HÁBITOS
# =====================================================================

class ConditionCatalogItem(BaseModel):
    id: str
    code: str
    type: str
    name: str
    description: Optional[str] = None

    class Config:
        from_attributes = True


class HabitEvaluationItem(BaseModel):
    habit: str  # AGUA, FRUTAS, BEBIDAS_AZUCARADAS, SUENO
    current_value: float
    required_value: float
    operator: str
    unit: str
    fulfilled: bool
    feedback: str


class HabitEvaluationResult(BaseModel):
    patient_id: str
    patient_name: str
    evaluation_status: str  # TODO_BIEN, HABITOS_POR_MEJORAR
    total_evaluated: int
    unfulfilled_count: int
    items: List[HabitEvaluationItem]
    notification_message: str
    evaluated_at: datetime


class AutomationConfigResponse(BaseModel):
    key: str
    is_active: bool
    cron_expr: str
    alert_threshold: int
    last_run_at: Optional[datetime] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class AutomationConfigUpdate(BaseModel):
    is_active: Optional[bool] = None
    cron_expr: Optional[str] = None
    alert_threshold: Optional[int] = None


class DeviceTokenCreate(BaseModel):
    token: str = Field(..., min_length=10, max_length=500)
    platform: str = Field("android", description="android, ios, web")
