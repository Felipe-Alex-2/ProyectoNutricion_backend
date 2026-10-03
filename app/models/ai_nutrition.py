import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class ConditionCatalog(Base):
    """Catálogo de condiciones clínicas (alergias e intolerancias, patologías/antecedentes)."""
    __tablename__ = "condition_catalog"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)  # LACTOSA, GLUTEN, DIABETES, HIPERTENSION, etc.
    type = Column(String(30), nullable=False)  # ALERGIA, ANTECEDENTE
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)


class AnamnesisCondition(Base):
    """Relación N:M entre Anamnesis y Catálogo de Condiciones."""
    __tablename__ = "anamnesis_conditions"

    anamnesis_id = Column(String(36), ForeignKey("patient_anamnesis.id", ondelete="CASCADE"), primary_key=True)
    condition_id = Column(String(36), ForeignKey("condition_catalog.id", ondelete="CASCADE"), primary_key=True)


class Food(Base):
    """Catálogo de alimentos base para el sistema experto."""
    __tablename__ = "foods"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    name = Column(String(120), unique=True, nullable=False, index=True)
    category = Column(String(50), nullable=True)  # LACTEOS, CEREALES, PROTEINAS, FRUTAS, VERDURAS, etc.
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    tags = relationship("FoodTag", back_populates="food", cascade="all, delete-orphan")


class FoodTag(Base):
    """Etiquetas nutricionales asociadas a cada alimento (LACTOSA, GLUTEN, AZUCAR_ALTO, SODIO_ALTO, etc.)."""
    __tablename__ = "food_tags"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    food_id = Column(String(36), ForeignKey("foods.id", ondelete="CASCADE"), nullable=False, index=True)
    tag = Column(String(50), nullable=False, index=True)

    food = relationship("Food", back_populates="tags")


class ExclusionRule(Base):
    """Reglas de exclusión del sistema experto: condición clínica -> etiqueta excluida."""
    __tablename__ = "exclusion_rules"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    condition_code = Column(String(50), nullable=False, index=True)  # ej. LACTOSA, DIABETES, HIPERTENSION
    excluded_tag = Column(String(50), nullable=False, index=True)  # ej. LACTOSA, AZUCAR_ALTO, SODIO_ALTO
    reason = Column(String(200), nullable=True)


class HabitParameter(Base):
    """Parámetros estándar de evaluación semanal de hábitos saludables."""
    __tablename__ = "habit_parameters"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    habit = Column(String(50), unique=True, nullable=False, index=True)  # AGUA, FRUTAS, BEBIDAS_AZUCARADAS, SUENO
    operator = Column(String(5), nullable=False)  # >=, <=
    value = Column(Float, nullable=False)
    unit = Column(String(20), default="", nullable=False)
    description = Column(String(200), nullable=True)


class AutomationConfig(Base):
    """Configuración de automatizaciones y RPA (recordatorios, avisos semanales, resúmenes)."""
    __tablename__ = "automation_configs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    key = Column(String(50), unique=True, nullable=False, index=True)  # AVISO_SEMANAL_HABITOS, RECORDATORIO_CITAS, etc.
    is_active = Column(Boolean, default=True, nullable=False)
    cron_expr = Column(String(50), default="0 9 * * 1", nullable=False)
    alert_threshold = Column(Integer, default=3, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    description = Column(String(200), nullable=True)


class NutritionalPlan(Base):
    """Plan nutricional generado (borrador IA o aprobado por nutricionista)."""
    __tablename__ = "nutritional_plans"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nutritionist_id = Column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(20), default="DRAFT", nullable=False)  # DRAFT, APPROVED, REJECTED
    title = Column(String(200), default="Plan Nutricional Personalizado", nullable=False)
    goal = Column(String(100), default="Pérdida de grasa", nullable=False)

    daily_calories = Column(Float, default=2000.0, nullable=False)
    protein_g = Column(Float, default=120.0, nullable=False)
    carbs_g = Column(Float, default=220.0, nullable=False)
    fats_g = Column(Float, default=60.0, nullable=False)
    meals_per_day = Column(Integer, default=4, nullable=False)

    meals_json = Column(Text, nullable=False)  # Lista de comidas estructuradas en JSON
    weekly_menu_json = Column(Text, nullable=True)  # Menú semanal de 7 días (JSON)
    clinical_notes = Column(Text, nullable=True)
    requires_special_review = Column(Boolean, default=False, nullable=False)

    approved_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient = relationship("User", foreign_keys=[patient_id])
    nutritionist = relationship("User", foreign_keys=[nutritionist_id])
    tenant = relationship("Tenant")


class ChatMessage(Base):
    """Historial de mensajes con el asistente nutricional 'Carlitos'."""
    __tablename__ = "chat_messages"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user, assistant
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = relationship("User", foreign_keys=[patient_id])


class FoodRecord(Base):
    """Registro y análisis por visión artificial de comidas del paciente."""
    __tablename__ = "food_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    image_url = Column(String(500), nullable=True)
    result_json = Column(Text, nullable=False)  # Detección completa de Gemini
    estimated_calories = Column(Float, default=0.0, nullable=False)
    estimated_carbs = Column(Float, default=0.0, nullable=False)
    estimated_protein = Column(Float, default=0.0, nullable=False)
    estimated_fats = Column(Float, default=0.0, nullable=False)
    confidence = Column(String(20), default="media", nullable=False)  # alta, media, baja
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    patient = relationship("User", foreign_keys=[patient_id])


class DeviceToken(Base):
    """Tokens de dispositivos para notificaciones push (FCM / móvil / web)."""
    __tablename__ = "device_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token = Column(String(500), unique=True, nullable=False, index=True)
    platform = Column(String(20), default="android", nullable=False)  # android, ios, web
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", foreign_keys=[user_id])
