from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, HttpUrl


class RecipeBase(BaseModel):
    title: str = Field(..., min_length=2, max_length=200, description="Nombre de la receta")
    description: Optional[str] = Field(None, description="Breve descripción o resumen")
    image_url: Optional[str] = Field(None, max_length=500, description="URL de la fotografía del platillo")

    calories: float = Field(0.0, ge=0, description="Calorías totales (kcal)")
    protein: float = Field(0.0, ge=0, description="Proteínas (g)")
    carbohydrates: float = Field(0.0, ge=0, description="Carbohidratos (g)")
    fats: float = Field(0.0, ge=0, description="Grasas totales (g)")
    fiber: float = Field(0.0, ge=0, description="Fibra (g)")
    sodium: Optional[float] = Field(0.0, ge=0, description="Sodio (mg)")

    servings: int = Field(1, ge=1, description="Número de porciones")
    prep_time_minutes: int = Field(15, ge=0, description="Tiempo de preparación en minutos")
    cook_time_minutes: int = Field(15, ge=0, description="Tiempo de cocción en minutos")
    difficulty: str = Field("Fácil", description="Dificultad: Fácil, Media, Difícil")
    category: str = Field("Almuerzo", description="Desayuno, Almuerzo, Cena, Snack, Bebida")

    ingredients: str = Field(..., min_length=3, description="Lista de ingredientes con cantidades")
    instructions: str = Field(..., min_length=5, description="Instrucciones paso a paso")


class RecipeCreate(RecipeBase):
    tenant_id: Optional[str] = None


class RecipeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    image_url: Optional[str] = None

    calories: Optional[float] = Field(None, ge=0)
    protein: Optional[float] = Field(None, ge=0)
    carbohydrates: Optional[float] = Field(None, ge=0)
    fats: Optional[float] = Field(None, ge=0)
    fiber: Optional[float] = Field(None, ge=0)
    sodium: Optional[float] = Field(None, ge=0)

    servings: Optional[int] = Field(None, ge=1)
    prep_time_minutes: Optional[int] = Field(None, ge=0)
    cook_time_minutes: Optional[int] = Field(None, ge=0)
    difficulty: Optional[str] = None
    category: Optional[str] = None

    ingredients: Optional[str] = None
    instructions: Optional[str] = None
    is_active: Optional[bool] = None


class RecipeResponse(RecipeBase):
    id: str
    tenant_id: Optional[str] = None
    created_by: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
