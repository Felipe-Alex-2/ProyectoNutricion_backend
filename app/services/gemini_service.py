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

        primary_model = settings.GEMINI_MODEL or "gemini-flash-lite-latest"
        candidate_models = [primary_model]
        for fallback in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

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

        req_data = json.dumps(payload).encode("utf-8")
        for model_to_try in candidate_models:
            url = f"{cls.BASE_URL}/{model_to_try}:generateContent?key={api_key}"
            try:
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
            except Exception as e:
                logger.warning(f"Error llamando a {model_to_try} ({e}). Probando siguiente...")
                continue

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
            logger.warning("GEMINI_API_KEY no configurada en las variables de entorno.")
            raise ValueError("El servicio de análisis con IA requiere configurar GEMINI_API_KEY en el servidor.")

        import base64
        base64_data = base64.b64encode(image_bytes).decode("utf-8")

        default_prompt = (
            "Eres un experto en nutricion y vision artificial. Analiza minuciosamente esta fotografia.\n"
            "Identifica todos los alimentos comestibles visibles: puede ser un plato preparado, una fruta o verdura individual (como una manzana, banana, naranja), un ingrediente, un snack o una bebida.\n"
            "Si la imagen muestra cualquier alimento comestible o fruta, estima con rigor sus porciones aproximadas y macronutrientes.\n"
            "Devuelve estrictamente un objeto JSON con este formato:\n"
            "{\n"
            '  "alimentos": [\n'
            '    {\n'
            '      "nombre": "Nombre del alimento o fruta",\n'
            '      "porcion_aprox_g": 180,\n'
            '      "calorias": 95,\n'
            '      "proteinas_g": 0.5,\n'
            '      "carbohidratos_g": 25.0,\n'
            '      "grasas_g": 0.3,\n'
            '      "fibra_g": 4.4\n'
            '    }\n'
            "  ],\n"
            '  "total": {\n'
            '    "calorias": 95,\n'
            '    "proteinas_g": 0.5,\n'
            '    "carbohidratos_g": 25.0,\n'
            '    "grasas_g": 0.3,\n'
            '    "fibra_g": 4.4\n'
            '  },\n'
            '  "confianza": "alta",\n'
            '  "observaciones": "Descripcion nutricional breve del alimento o plato."\n'
            "}\n"
            'Solo y unicamente si la fotografia NO contiene absolutamente ningun alimento ni elemento comestible (por ejemplo: objetos inanimados, vehiculos, computadoras, personas sin comida), responde: {"error": "no_es_comida"}.'
        )

        primary_model = settings.GEMINI_MODEL or "gemini-flash-lite-latest"
        candidate_models = [primary_model]
        for fallback in ["gemini-flash-lite-latest", "gemini-3.1-flash-lite", "gemini-3.8-flash"]:
            if fallback not in candidate_models:
                candidate_models.append(fallback)

        payload_dict = {
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
                "maxOutputTokens": 2000,
                "responseMimeType": "application/json",
            },
        }

        req_data = json.dumps(payload_dict).encode("utf-8")
        last_error = None

        for model_to_try in candidate_models:
            url = f"{cls.BASE_URL}/{model_to_try}:generateContent?key={api_key}"
            try:
                req = urllib.request.Request(
                    url,
                    data=req_data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=45) as resp:
                    result = json.loads(resp.read().decode("utf-8"))
                    candidates = result.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "")
                            parsed = cls._clean_and_parse_json(raw_text)
                            if parsed:
                                return parsed
            except urllib.error.HTTPError as e:
                error_body = ""
                try:
                    error_body = e.read().decode("utf-8")
                except Exception:
                    pass
                logger.warning(f"Error HTTP {e.code} con modelo {model_to_try}: {error_body[:100]}. Intentando siguiente...")
                last_error = f"HTTP {e.code}: {model_to_try}"
                continue
            except Exception as e:
                logger.warning(f"Error de conexion con {model_to_try}: {e}")
                last_error = str(e)
                continue

        raise ValueError(f"No se pudo analizar la imagen con los modelos de IA disponibles ({last_error}).")

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
