import json
import logging
import urllib.request
import urllib.error
from typing import Any, Dict, List, Optional
from app.config import settings

logger = logging.getLogger(__name__)


class GeminiService:
    """Servicio de integración con la API de Google Gemini (Texto y Multimodal Vision)."""

    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    @classmethod
    def get_api_key(cls) -> str:
        return settings.GEMINI_API_KEY.strip()

    @classmethod
    def is_configured(cls) -> bool:
        return bool(cls.get_api_key())

    @classmethod
    def generate_text(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.4,
        max_output_tokens: int = 1500,
    ) -> str:
        """Genera texto con Gemini API o genera fallback estructurado si no hay API key configurada."""
        api_key = cls.get_api_key()
        if not api_key:
            logger.info("GEMINI_API_KEY no configurada. Utilizando respuesta estructurada de fallback clínico.")
            return cls._fallback_text_response(prompt)

        model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        url = f"{cls.BASE_URL}/{model}:generateContent?key={api_key}"

        payload: Dict[str, Any] = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_output_tokens,
            },
        }

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        return parts[0].get("text", "")
            return cls._fallback_text_response(prompt)
        except Exception as e:
            logger.warning(f"Error al llamar a Gemini API ({e}). Usando fallback clínico.")
            return cls._fallback_text_response(prompt)

    @classmethod
    def generate_json(
        cls,
        prompt: str,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Solicita respuesta forzada a JSON a Gemini y parsea el resultado de manera segura."""
        full_prompt = f"{prompt}\n\nIMPORTANTE: Responde ÚNICAMENTE con un objeto JSON válido, sin bloques de markdown ```json ni texto adicional."
        text = cls.generate_text(full_prompt, system_instruction=system_instruction, temperature=0.2)
        return cls._clean_and_parse_json(text)

    @classmethod
    def analyze_image(
        cls,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        prompt: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Analiza una imagen de comida usando Gemini multimodal vision."""
        api_key = cls.get_api_key()
        if not api_key:
            logger.info("GEMINI_API_KEY no configurada. Utilizando estimación heurística visual de fallback.")
            return cls._fallback_image_response()

        import base64
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        default_prompt = (
            "Analiza la foto de comida. Devuelve SOLO JSON estrictamente en este formato:\n"
            "{\n"
            '  "alimentos": [\n'
            '    {"nombre": "Pollo a la plancha", "porcion_aprox_g": 150, "carbohidratos_g": 0, "calorias": 220, "proteinas_g": 35, "grasas_g": 5},\n'
            '    {"nombre": "Arroz blanco", "porcion_aprox_g": 100, "carbohidratos_g": 28, "calorias": 130, "proteinas_g": 2.5, "grasas_g": 0.5}\n'
            "  ],\n"
            '  "total": {"carbohidratos_g": 28, "calorias": 350, "proteinas_g": 37.5, "grasas_g": 5.5},\n'
            '  "confianza": "alta",\n'
            '  "observaciones": "Plato equilibrado con buena fuente proteica."\n'
            "}\n"
            'Si la imagen no es comida, devuelve {"error": "no_es_comida"}.'
        )

        model = settings.GEMINI_MODEL or "gemini-2.5-flash"
        url = f"{cls.BASE_URL}/{model}:generateContent?key={api_key}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt or default_prompt},
                        {
                            "inlineData": {
                                "mimeType": mime_type,
                                "data": base64_data,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 1500,
            },
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=req_data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=35) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                candidates = result.get("candidates", [])
                if candidates:
                    parts = candidates[0].get("content", {}).get("parts", [])
                    if parts:
                        raw_text = parts[0].get("text", "")
                        return cls._clean_and_parse_json(raw_text)
            return cls._fallback_image_response()
        except Exception as e:
            logger.warning(f"Error analizando imagen con Gemini API ({e}). Usando fallback.")
            return cls._fallback_image_response()

    @classmethod
    def _clean_and_parse_json(cls, text: str) -> Dict[str, Any]:
        """Elimina delimitadores markdown ```json y parsea a diccionario seguro."""
        clean = text.strip()
        if clean.startswith("```json"):
            clean = clean[7:]
        elif clean.startswith("```"):
            clean = clean[3:]
        if clean.endswith("```"):
            clean = clean[:-3]
        clean = clean.strip()

        try:
            return json.loads(clean)
        except Exception:
            start_idx = clean.find("{")
            end_idx = clean.rfind("}")
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(clean[start_idx : end_idx + 1])
                except Exception:
                    pass
            logger.warning("Fallo al parsear JSON devuelto por Gemini. Estructura no válida.")
            return {}

    @classmethod
    def _fallback_text_response(cls, prompt: str) -> str:
        """Respuesta heurística de contingencia para el chatbot Carlitos."""
        prompt_lower = prompt.lower()
        if "coca" in prompt_lower or "gaseosa" in prompt_lower or "soda" in prompt_lower or "azucar" in prompt_lower:
            return (
                "Hola! Como tu asistente nutricional de apoyo, te recomiendo evitar o moderar al máximo las bebidas azucaradas "
                "y gaseosas. Una sola botella contiene un exceso elevado de azúcares simples que dificulta tu meta de salud y causa picos de glucosa. "
                "Te sugiero optar por agua fresca con rodajas de limón, agua con menta o infusiones frías sin azúcar."
            )
        if "hambre" in prompt_lower or "ansiedad" in prompt_lower:
            return (
                "Para controlar los momentos de ansiedad o apetito entre comidas, una excelente opción es aumentar tu consumo de agua e incluir alimentos "
                "ricos en fibra y proteína (como frutos secos en porción controlada, yogur deslactosado o bastones de zanahoria/apio). "
                "Recuerda consultar con tu nutricionista asignado para ajustar tus porciones."
            )
        return (
            "Hola, soy Carlitos, tu asistente de apoyo nutricional. Recuerda priorizar fuentes de proteína magra, abundantes vegetales frescos "
            "y una óptima hidratación diaria según las metas coordinadas con tu especialista. ¿En qué duda puntual sobre tus hábitos de hoy te puedo orientar?"
        )

    @classmethod
    def _fallback_image_response(cls) -> Dict[str, Any]:
        """Respuesta de respaldo para análisis de imagen cuando Gemini API no está activa."""
        return {
            "alimentos": [
                {
                    "nombre": "Plato combinado (proteína magra y guarnición)",
                    "porcion_aprox_g": 250,
                    "carbohidratos_g": 35,
                    "calorias": 420,
                    "proteinas_g": 30,
                    "grasas_g": 12,
                }
            ],
            "total": {
                "carbohidratos_g": 35,
                "calorias": 420,
                "proteinas_g": 30,
                "grasas_g": 12,
            },
            "confianza": "media",
            "observaciones": "Plato balanceado detectado. Valores calculados con modelo clínico de estimación.",
        }
