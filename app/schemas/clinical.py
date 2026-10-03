from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- ANAMNESIS ---
class AnamnesisBase(BaseModel):
    # Datos biométricos y ML
    birth_date: Optional[datetime] = Field(None, description="Fecha de nacimiento para cálculo de edad")
    gender: str = Field("M", description="Sexo biológico (M/F)")
    weight_kg: Optional[float] = Field(70.0, ge=20.0, le=400.0, description="Peso actual en kg")
    height_cm: Optional[float] = Field(170.0, ge=50.0, le=260.0, description="Talla en cm")
    target_weight_kg: Optional[float] = Field(None, ge=20.0, le=400.0, description="Peso objetivo en kg")
    target_weeks: Optional[int] = Field(None, ge=1, le=104, description="Plazo objetivo en semanas")

    # Antecedentes y alergias
    pathologies: Optional[str] = Field(None, description="Antecedentes patológicos (diabetes, hipertensión, etc.)")
    allergies: Optional[str] = Field(None, description="Alergias e intolerancias (lactosa, gluten, etc.)")
    medications: Optional[str] = Field(None, description="Fármacos y suplementos actuales")
    other_allergies: Optional[str] = Field(None, description="Otros alérgenos especificados")
    other_pathologies: Optional[str] = Field(None, description="Otras condiciones patológicas")

    # Hábitos de vida y estilo
    water_intake_liters: float = Field(1.5, ge=0.0, le=10.0, description="Consumo diario de agua en litros")
    alcohol_frequency: str = Field("Nunca", description="Nunca, Ocasional, Frecuente")
    smoke_habit: str = Field("No fuma", description="No fuma, Ocasional, Habitual")
    coffee_cups: int = Field(1, ge=0, le=20, description="Tazas de café/día")
    sleep_hours: float = Field(7.0, ge=1.0, le=24.0, description="Horas de sueño promedio")

    # Porciones y sistema experto
    fruits_vegetables_daily: Optional[int] = Field(3, ge=0, le=20, description="Porciones de frutas/verduras al día")
    sugary_drinks_weekly: Optional[int] = Field(0, ge=0, le=100, description="Bebidas azucaradas consumidas por semana")
    meals_per_day: Optional[int] = Field(4, ge=1, le=10, description="Número de comidas por día")
    is_pregnant_or_lactating: Optional[bool] = Field(False, description="Condición de embarazo o lactancia")

    # Actividad física y digestión
    physical_activity: str = Field("Ligero", description="Sedentario, Ligero, Moderado, Intenso")
    digestive_symptoms: Optional[str] = Field(None, description="Síntomas digestivos recurrentes")
    food_preferences: Optional[str] = Field(None, description="Preferencias o aversiones de alimentos")
    goal: str = Field("Pérdida de grasa", min_length=2, max_length=200, description="Objetivo principal del paciente")
    consent_data_processing: bool = Field(True, description="Consentimiento legal para tratamiento de datos de salud")


class AnamnesisCreateOrUpdate(AnamnesisBase):
    pass


class AnamnesisResponse(AnamnesisBase):
    id: str
    patient_id: str
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# --- HISTORIAL CLÍNICO ---
class ClinicalRecordBase(BaseModel):
    diagnosis: str = Field(..., min_length=3, description="Diagnóstico nutricional y clínico")
    evolution_notes: Optional[str] = Field(None, description="Notas de consulta y evolución")
    clinical_goals: Optional[str] = Field(None, description="Metas clínicas acordadas")


class ClinicalRecordCreateOrUpdate(ClinicalRecordBase):
    pass


class ClinicalRecordResponse(ClinicalRecordBase):
    id: str
    patient_id: str
    nutritionist_id: str
    tenant_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
