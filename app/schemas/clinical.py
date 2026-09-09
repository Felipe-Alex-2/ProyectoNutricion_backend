from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# --- ANAMNESIS ---
class AnamnesisBase(BaseModel):
    pathologies: Optional[str] = Field(None, description="Antecedentes patológicos (diabetes, hipertensión, etc.)")
    allergies: Optional[str] = Field(None, description="Alergias e intolerancias (lactosa, gluten, etc.)")
    medications: Optional[str] = Field(None, description="Fármacos y suplementos actuales")

    water_intake_liters: float = Field(1.5, ge=0.0, le=10.0, description="Consumo diario de agua en litros")
    alcohol_frequency: str = Field("Nunca", description="Nunca, Ocasional, Frecuente")
    smoke_habit: str = Field("No fuma", description="No fuma, Ocasional, Habitual")
    coffee_cups: int = Field(1, ge=0, le=20, description="Tazas de café/día")
    sleep_hours: float = Field(7.0, ge=1.0, le=24.0, description="Horas de sueño promedio")

    physical_activity: str = Field("Ligero", description="Sedentario, Ligero, Moderado, Intenso")
    digestive_symptoms: Optional[str] = Field(None, description="Síntomas digestivos recurrentes")
    food_preferences: Optional[str] = Field(None, description="Preferencias o aversiones de alimentos")
    goal: str = Field("Pérdida de grasa", min_length=2, max_length=200, description="Objetivo principal del paciente")


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
