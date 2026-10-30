"""Endpoints de Visión por Computadora para análisis de platos de comida."""
from typing import List, Optional
import hashlib
import json
import uuid
from fastapi import Form, Query
from sqlalchemy.exc import IntegrityError
from starlette.concurrency import run_in_threadpool
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.services.food_vision_service import FoodVisionService
from app.schemas.ai_nutrition import FoodAnalysisResponse, FoodRecordResponse, FoodRecordCreate
from app.models.ai_nutrition import FoodRecord
from app.core.authorization import require_patient_access

router = APIRouter(prefix="/food", tags=["Visión Artificial - Análisis de Comidas"])


@router.post("/analyze", response_model=FoodAnalysisResponse)
async def analyze_food_photo(
    file: UploadFile = File(...),
    patient_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Sube una fotografía de plato de comida y recibe la estimación nutricional automática
    (alimentos identificados, calorías, carbohidratos, proteínas, grasas y comparación con su objetivo diario).
    """
    target_id = patient_id or current_user.id
    require_patient_access(db, current_user, target_id, allow_self=True)
    # Validar formato
    mime = file.content_type or "image/jpeg"
    if not (mime.startswith("image/") or (file.filename or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El archivo debe ser una imagen válida (JPG, PNG, WebP).")

    contents = await file.read(10 * 1024 * 1024 + 1)
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
    else:
        raise HTTPException(status_code=400, detail="La imagen no tiene un formato válido (JPG, PNG, WebP, HEIC).")

    try:
        result = await run_in_threadpool(FoodVisionService.analyze_food_image,
            db=db,
            patient_id=target_id,
            image_bytes=contents,
            mime_type=mime,
            image_url=file.filename,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="No se pudo analizar la imagen. Intenta nuevamente o registra la comida manualmente.")


@router.get("/history", response_model=List[FoodRecordResponse])
def get_food_history(
    patient_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consulta el historial de platos analizados por el paciente."""
    target_id = patient_id or current_user.id
    require_patient_access(db, current_user, target_id, allow_self=True)
    return FoodVisionService.get_patient_food_history(db=db, patient_id=target_id, limit=100)


@router.post('/records', response_model=FoodRecordResponse, status_code=201)
def register_food(data: FoodRecordCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Persist a self-reported meal exactly once, including after a lost response."""
    record_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f'food:{current_user.id}:{data.client_record_id}'))
    payload = data.model_dump(mode='json')
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    def response(record):
        details = json.loads(record.result_json)
        if details.get('fingerprint') != fingerprint:
            raise HTTPException(409, 'Este identificador ya pertenece a otro registro de alimentación.')
        return FoodRecordResponse.model_validate(record).model_copy(update={'details': details})

    existing = db.get(FoodRecord, record_id)
    if existing:
        return response(existing)
    record = FoodRecord(
        id=record_id, patient_id=current_user.id,
        result_json=json.dumps({'source': 'manual', 'fingerprint': fingerprint, **payload}),
        estimated_calories=data.calories, estimated_protein=data.protein_g,
        estimated_carbs=data.carbs_g, estimated_fats=data.fats_g,
        confidence='manual', notes=f'{data.meal_type}: {data.description}',
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.get(FoodRecord, record_id)
        if existing is None:
            raise
        return response(existing)
    db.refresh(record)
    return response(record)
