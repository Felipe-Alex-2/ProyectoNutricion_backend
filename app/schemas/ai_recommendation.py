from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class RecipeRecommendationItem(BaseModel):
    recipe_id: str
    recipe_title: str
    category: str
    calories: float
    protein: float
    carbohydrates: float
    fats: float
    fiber: float
    match_score: int = Field(..., ge=0, le=100, description="Puntaje de compatibilidad 0-100%")
    compatibility_level: str = Field(..., description="ALTA, MEDIA, PRECAUCION, CONTRAINDICADA")
    reasons: List[str] = Field(default_factory=list, description="Razones clínicas y nutricionales de compatibilidad")
    warnings: List[str] = Field(default_factory=list, description="Alertas sobre alérgenos o patologías")
    clinical_notes: Optional[str] = Field(None, description="Recomendación de porción o momento")
    already_assigned: bool = False


class AIRecommendationResponse(BaseModel):
    patient_id: str
    patient_name: str
    patient_goal: Optional[str] = None
    known_pathologies: Optional[str] = None
    known_allergies: Optional[str] = None
    summary_analysis: str
    generated_at: datetime
    recommendations: List[RecipeRecommendationItem]
