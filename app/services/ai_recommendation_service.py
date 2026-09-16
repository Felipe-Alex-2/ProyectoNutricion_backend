import os
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.clinical import PatientAnamnesis, ClinicalRecord
from app.models.recipe import Recipe, RecipeAssignment
from app.schemas.ai_recommendation import AIRecommendationResponse, RecipeRecommendationItem

logger = logging.getLogger(__name__)


class AIRecommendationService:

    @classmethod
    def recommend_for_patient(
        cls,
        db: Session,
        patient_id: str,
        nutritionist_id: Optional[str] = None,
    ) -> AIRecommendationResponse:
        """
        Analiza de forma inteligente el perfil clínico del paciente (anamnesis, metas,
        alergias, patologías y evolución) y evalúa todas las recetas disponibles
        generando compatibilidad porcentual, alertas y justificación clínica.
        """
        patient = db.query(User).filter(User.id == patient_id).first()
        if not patient:
            raise ValueError("Paciente no encontrado")

        anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()
        records = (
            db.query(ClinicalRecord)
            .filter(ClinicalRecord.patient_id == patient_id)
            .order_by(ClinicalRecord.created_at.desc())
            .all()
        )

        assigned_recipe_ids = set(
            row[0]
            for row in db.query(RecipeAssignment.recipe_id)
            .filter(RecipeAssignment.patient_id == patient_id)
            .all()
        )

        # Buscar recetas accesibles para el paciente / nutricionista
        recipe_query = db.query(Recipe).filter(Recipe.is_active == True)
        if patient.tenant_id:
            recipe_query = recipe_query.filter(
                (Recipe.tenant_id == patient.tenant_id) | (Recipe.tenant_id == None)
            )
        recipes = recipe_query.all()

        # Extraer variables clínicas
        goal = (anamnesis.goal if anamnesis and anamnesis.goal else "Salud general").lower()
        pathologies = (anamnesis.pathologies if anamnesis and anamnesis.pathologies else "").lower()
        allergies = (anamnesis.allergies if anamnesis and anamnesis.allergies else "").lower()
        activity = (anamnesis.physical_activity if anamnesis and anamnesis.physical_activity else "Moderado").lower()
        digestive = (anamnesis.digestive_symptoms if anamnesis and anamnesis.digestive_symptoms else "").lower()
        food_prefs = (anamnesis.food_preferences if anamnesis and anamnesis.food_preferences else "").lower()

        # Historial clínico consolidado
        latest_diagnosis = records[0].diagnosis if records else ""
        latest_goals = records[0].clinical_goals if records else ""

        recommendations: List[RecipeRecommendationItem] = []

        for r in recipes:
            score = 70  # Puntaje base
            reasons: List[str] = []
            warnings: List[str] = []
            contraindicated = False

            rec_ingredients = (r.ingredients or "").lower()
            rec_title = (r.title or "").lower()
            rec_desc = (r.description or "").lower()
            all_recipe_text = f"{rec_title} {rec_ingredients} {rec_desc}"

            # 1. EVALUACIÓN DE ALERGIAS E INTOLERANCIAS (FILTRO CRÍTICO)
            raw_tokens = [a.strip() for a in allergies.replace(";", ",").replace(" y ", ",").split(",") if a.strip()]
            for raw_token in raw_tokens:
                cleaned_token = raw_token
                for prefix in ["alérgica a la ", "alérgico a la ", "alérgica a ", "alérgico a ", "alergia a la ", "alergia a ", "intolerancia a la ", "intolerancia a "]:
                    if cleaned_token.startswith(prefix):
                        cleaned_token = cleaned_token[len(prefix):].strip()
                if len(cleaned_token) < 3:
                    continue
                if cleaned_token in all_recipe_text or any(word in all_recipe_text for word in cleaned_token.split() if len(word) > 3):
                    score = 0
                    contraindicated = True
                    warnings.append(f"ALERTA CRÍTICA: Contiene o menciona alérgeno identificado: '{cleaned_token.capitalize()}'.")

            # Alérgenos comunes específicos
            if "gluten" in allergies or "celiac" in pathologies or "celíac" in pathologies:
                if any(w in all_recipe_text for w in ["trigo", "harina de trigo", "pan", "avena regular", "cebada", "centeno"]):
                    score = 0
                    contraindicated = True
                    warnings.append("Contraindicada por presencia de gluten para paciente con condición celíaca o intolerancia.")

            if "lactosa" in allergies or "lácteo" in allergies or "leche" in allergies:
                if any(w in all_recipe_text for w in ["leche", "queso", "crema", "mantequilla", "yogur"]):
                    if "sin lactosa" not in all_recipe_text and "deslactosad" not in all_recipe_text:
                        score -= 40
                        warnings.append("Contiene lácteos que pueden causar malestar si no se utiliza sustituto deslactosado.")

            # 2. EVALUACIÓN DE PATOLOGÍAS CLÍNICAS
            if "hipertens" in pathologies or "presion alta" in pathologies:
                if (r.sodium or 0) > 400 or "sal" in rec_ingredients:
                    score -= 20
                    warnings.append("Vigilar contenido de sodio para paciente hipertenso (se sugiere reducir sal agregada).")
                else:
                    score += 8
                    reasons.append("Bajo perfil de sodio, favorable para control de tensión arterial.")

            if "diabet" in pathologies or "resistencia a la insulina" in pathologies:
                if (r.carbohydrates or 0) > 45 and (r.fiber or 0) < 4:
                    score -= 25
                    warnings.append("Carga glucémica moderada-alta; priorizar fibra para amortiguar índice glucémico.")
                elif (r.fiber or 0) >= 4:
                    score += 12
                    reasons.append("Excelente aporte de fibra (>=4g) que estabiliza la respuesta insulínica.")

            if "colesterol" in pathologies or "dislipidem" in pathologies or "triglicerid" in pathologies:
                if (r.fats or 0) > 20:
                    score -= 15
                    warnings.append("Monitorear grasas totales en perfil lipídico alterado.")
                else:
                    score += 7
                    reasons.append("Perfil lipídico controlado, adecuado para salud cardiovascular.")

            if any(s in digestive for s in ["gastritis", "acidez", "reflujo"]):
                if any(w in all_recipe_text for w in ["picante", "chile", "ají", "pimienta negra", "café", "tomate frito"]):
                    score -= 20
                    warnings.append("Puede irritar la mucosa gástrica debido a condimentos o acidez.")

            # 3. EVALUACIÓN DE OBJETIVOS NUTRICIONALES
            if "pérdida" in goal or "grasa" in goal or "peso" in goal or "deficit" in goal:
                if r.calories <= 450:
                    score += 15
                    reasons.append(f"Densidad calórica moderada ({r.calories} kcal) óptima para déficit controlado.")
                if (r.protein or 0) >= 20:
                    score += 12
                    reasons.append(f"Aporte proteico ({r.protein}g) para preservar masa magra durante la pérdida de grasa.")
                if r.calories > 650:
                    score -= 15
                    warnings.append(f"Calorías elevadas ({r.calories} kcal) para objetivo de déficit calórico.")

            elif "muscul" in goal or "volumen" in goal or "hipertrofia" in goal:
                if (r.protein or 0) >= 25:
                    score += 18
                    reasons.append(f"Alto contenido proteico ({r.protein}g) ideal para síntesis muscular.")
                if r.calories >= 450:
                    score += 10
                    reasons.append("Aporte energético suficiente para superávit calórico controlado.")

            # 4. PREFERENCIAS DEL PACIENTE
            if food_prefs:
                for pref in [p.strip() for p in food_prefs.split(",") if len(p.strip()) > 2]:
                    if pref in all_recipe_text:
                        score += 5
                        reasons.append(f"Coincide con preferencia del paciente: '{pref.capitalize()}'.")

            # Limitar score a rango 0 - 100
            final_score = max(0, min(100, score))
            if contraindicated:
                final_score = 0
                level = "CONTRAINDICADA"
            elif final_score >= 80:
                level = "ALTA"
            elif final_score >= 60:
                level = "MEDIA"
            else:
                level = "PRECAUCION"

            if not reasons and not warnings:
                reasons.append("Plato equilibrado con macronutrientes estándar.")

            clinical_note = (
                f"Sugerencia: Categoría {r.category}. {r.servings} porción(es) de {r.calories} kcal con {r.protein}g de proteína."
            )

            is_assigned = r.id in assigned_recipe_ids

            recommendations.append(
                RecipeRecommendationItem(
                    recipe_id=r.id,
                    recipe_title=r.title,
                    category=r.category,
                    calories=r.calories,
                    protein=r.protein,
                    carbohydrates=r.carbohydrates,
                    fats=r.fats,
                    fiber=r.fiber,
                    match_score=final_score,
                    compatibility_level=level,
                    reasons=reasons,
                    warnings=warnings,
                    clinical_notes=clinical_note,
                    already_assigned=is_assigned,
                )
            )

        # Ordenar recomendaciones de mayor compatibilidad a menor
        recommendations.sort(key=lambda x: (not x.already_assigned, x.match_score), reverse=True)

        summary = (
            f"Análisis IA Nutricional para {patient.full_name}: "
            f"Objetivo principal '{anamnesis.goal if anamnesis else 'General'}' con "
            f"nivel de actividad '{anamnesis.physical_activity if anamnesis else 'Moderado'}'. "
            f"Se evaluaron {len(recipes)} recetas del catálogo filtrando alérgenos y patologías conocidas."
        )

        return AIRecommendationResponse(
            patient_id=patient.id,
            patient_name=patient.full_name,
            patient_goal=anamnesis.goal if anamnesis else None,
            known_pathologies=anamnesis.pathologies if anamnesis else None,
            known_allergies=anamnesis.allergies if anamnesis else None,
            summary_analysis=summary,
            generated_at=datetime.now(timezone.utc),
            recommendations=recommendations,
        )
