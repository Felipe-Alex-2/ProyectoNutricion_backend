"""Endpoints de Visión por Computadora para análisis de platos de comida."""
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.food_vision_service import FoodVisionService
from app.schemas.ai_nutrition import FoodAnalysisResponse, FoodRecordResponse

router = APIRouter(prefix="/food", tags=["Visión Artificial - Análisis de Comidas"])


@router.post("/analyze", response_model=FoodAnalysisResponse)
async def analyze_food_photo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sube una fotografía de plato de comida y recibe la estimación nutricional automática
    (alimentos identificados, calorías, carbohidratos, proteínas, grasas y comparación con su objetivo diario).
    """
    # Validar formato
    mime = file.content_type or "image/jpeg"
    if not (mime.startswith("image/") or file.filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser una imagen válida (JPG, PNG, WebP).")

    contents = await file.read()
    if len(contents) > 10 * 1024 * 1024:  # 10 MB límite seguro
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La imagen no debe superar los 10 MB.")

    # Flutter envia el archivo como application/octet-stream; Gemini necesita el tipo real.
    if contents[:8] == b"\x89PNG\r\n\x1a\n":
        mime = "image/png"
    elif contents[:3] == b"\xff\xd8\xff":
        mime = "image/jpeg"
    elif contents[:4] == b"RIFF" and contents[8:12] == b"WEBP":
        mime = "image/webp"
    elif contents[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftypmsf1"):
        mime = "image/heic"
    elif not mime.startswith("image/"):
        mime = "image/jpeg"

    try:
        result = FoodVisionService.analyze_food_image(
            db=db,
            patient_id=current_user.id,
            image_bytes=contents,
            mime_type=mime,
            image_url=file.filename,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error analizando comida: {str(e)}")


@router.get("/history", response_model=List[FoodRecordResponse])
def get_food_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consulta el historial de platos analizados por el paciente."""
    return FoodVisionService.get_patient_food_history(db=db, patient_id=current_user.id)
