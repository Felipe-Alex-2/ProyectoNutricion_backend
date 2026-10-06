import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.clinical import PatientAnamnesis
from app.models.ai_nutrition import FoodRecord, NutritionalPlan
from app.services.gemini_service import GeminiService
from app.schemas.ai_nutrition import (
    FoodAnalysisResponse,
    DetectedFood,
    FoodAnalysisTotals,
    FoodAnalysisEvaluation,
    FoodRecordResponse,
)

logger = logging.getLogger(__name__)


class FoodVisionService:
    """Servicio de análisis visual nutricional de alimentos mediante Gemini Multimodal."""

    @classmethod
    def analyze_food_image(
        cls,
        db: Session,
        patient_id: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        image_url: Optional[str] = None,
    ) -> FoodAnalysisResponse:
        """
        Envía la foto a Gemini multimodal, parsea macronutrientes,
        evalúa contra el objetivo del paciente y guarda en historial clínico.
        """
        # 1. Llamar a Gemini Vision
        analysis_data = GeminiService.analyze_image(
            image_bytes=image_bytes,
            mime_type=mime_type,
        )

        if "error" in analysis_data and analysis_data["error"] == "no_es_comida":
            raise ValueError("La imagen enviada no parece contener alimentos detectables. Intenta con una toma más clara de tu plato o alimento.")

        # 2. Parsear alimentos detectados
        raw_alimentos = analysis_data.get("alimentos", [])
        alimentos_list: List[DetectedFood] = []
        for item in raw_alimentos:
            alimentos_list.append(
                DetectedFood(
                    nombre=item.get("nombre", "Alimento identificado"),
                    porcion_aprox_g=float(item.get("porcion_aprox_g", 0.0)),
                    carbohidratos_g=float(item.get("carbohidratos_g", 0.0)),
                    calorias=float(item.get("calorias", 0.0)),
                    proteinas_g=float(item.get("proteinas_g", 0.0)),
                    grasas_g=float(item.get("grasas_g", 0.0)),
                    fibra_g=float(item.get("fibra_g", 0.0)),
                )
            )

        if not alimentos_list:
            raise ValueError("No se detectaron alimentos con suficiente claridad. Intenta con una toma más cercana o mejor iluminada.")

        raw_total = analysis_data.get("total", {})
        totals = FoodAnalysisTotals(
            calorias=float(raw_total.get("calorias", sum(f.calorias for f in alimentos_list))),
            carbohidratos_g=float(raw_total.get("carbohidratos_g", sum(f.carbohidratos_g for f in alimentos_list))),
            proteinas_g=float(raw_total.get("proteinas_g", sum(f.proteinas_g for f in alimentos_list))),
            grasas_g=float(raw_total.get("grasas_g", sum(f.grasas_g for f in alimentos_list))),
            fibra_g=float(raw_total.get("fibra_g", sum(f.fibra_g for f in alimentos_list))),
        )

        confidence = analysis_data.get("confianza", "media")
        observations = analysis_data.get("observaciones", "Plato analizado correctamente.")

        # 3. Comparación con meta calórica diaria del paciente
        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        active_plan = (
            db.query(NutritionalPlan)
            .filter(NutritionalPlan.patient_id == patient_id, NutritionalPlan.status == "APPROVED")
            .first()
        )

        target_daily_kcal = active_plan.daily_calories if active_plan else 2000.0
        meals_per_day = active_plan.meals_per_day if active_plan else (anamnesis.meals_per_day if anamnesis else 4) or 4
        recommended_meal_kcal = round(target_daily_kcal / meals_per_day, 1)

        # Regla simple de evaluación
        cal_diff = totals.calorias - recommended_meal_kcal
        if cal_diff > (recommended_meal_kcal * 0.35):
            eval_status = "EXCESO_CALORICO_MODERADO"
            eval_msg = (
                f"Esta comida aporta {totals.calorias} kcal (~{round(cal_diff)} kcal por encima de la porción media sugerida de {recommended_meal_kcal} kcal). "
                "Te sugerimos equilibrar reduciendo carbohidratos simples en tu siguiente comida."
            )
        elif cal_diff < -(recommended_meal_kcal * 0.4):
            eval_status = "DEFICIT_CALORICO"
            eval_msg = (
                f"Aporte ligero ({totals.calorias} kcal frente a {recommended_meal_kcal} kcal sugeridas). "
                "Asegúrate de no omitir proteínas para evitar fatiga o pérdida muscular."
            )
        else:
            eval_status = "OPTIMO"
            eval_msg = f"¡Excelente! Esta comida de {totals.calorias} kcal encaja perfectamente con tu meta por toma ({recommended_meal_kcal} kcal)."

        evaluation = FoodAnalysisEvaluation(
            status=eval_status,
            daily_target_calories=target_daily_kcal,
            meal_recommended_calories=recommended_meal_kcal,
            comparison_message=eval_msg,
        )

        # 4. Almacenar registro en la BD
        record = FoodRecord(
            patient_id=patient_id,
            image_url=image_url,
            result_json=json.dumps(analysis_data, ensure_ascii=False),
            estimated_calories=totals.calorias,
            estimated_carbs=totals.carbohidratos_g,
            estimated_protein=totals.proteinas_g,
            estimated_fats=totals.grasas_g,
            estimated_fiber=totals.fibra_g,
            confidence=confidence,
            notes=observations,
            created_at=datetime.now(timezone.utc),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        return FoodAnalysisResponse(
            record_id=record.id,
            alimentos=alimentos_list,
            total=totals,
            confianza=confidence,
            observaciones=observations,
            evaluacion=evaluation,
            image_url=image_url,
            created_at=record.created_at,
        )

    @classmethod
    def get_patient_food_history(
        cls,
        db: Session,
        patient_id: str,
        limit: int = 20,
    ) -> List[FoodRecordResponse]:
        """Obtiene las comidas fotografiadas y analizadas recientemente."""
        records = (
            db.query(FoodRecord)
            .filter(FoodRecord.patient_id == patient_id)
            .order_by(FoodRecord.created_at.desc())
            .limit(limit)
            .all()
        )
        results = []
        for r in records:
            details = None
            try:
                details = json.loads(r.result_json) if r.result_json else None
            except Exception:
                pass

            results.append(
                FoodRecordResponse(
                    id=r.id,
                    patient_id=r.patient_id,
                    image_url=r.image_url,
                    estimated_calories=r.estimated_calories,
                    estimated_carbs=r.estimated_carbs,
                    estimated_protein=r.estimated_protein,
                    estimated_fats=r.estimated_fats,
                    estimated_fiber=getattr(r, "estimated_fiber", 0.0) or 0.0,
                    confidence=r.confidence,
                    notes=r.notes,
                    details=details,
                    created_at=r.created_at,
                )
            )
        return results
