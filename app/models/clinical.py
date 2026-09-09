import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class PatientAnamnesis(Base):
    __tablename__ = "patient_anamnesis"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)

    # Antecedentes médicos y alergias (Texto o listas separadas por comas)
    pathologies = Column(Text, nullable=True)  # Hipertensión, Diabetes, etc.
    allergies = Column(Text, nullable=True)  # Lactosa, Gluten, Mariscos, etc.
    medications = Column(Text, nullable=True)  # Fármacos o suplementos actuales

    # Hábitos de vida y estilo
    water_intake_liters = Column(Float, default=1.5, nullable=False)
    alcohol_frequency = Column(String(50), default="Nunca", nullable=False)  # Nunca, Ocasional, Frecuente
    smoke_habit = Column(String(50), default="No fuma", nullable=False)  # No fuma, Ocasional, Habitual
    coffee_cups = Column(Integer, default=1, nullable=False)
    sleep_hours = Column(Float, default=7.0, nullable=False)

    # Actividad física y digestión
    physical_activity = Column(String(50), default="Ligero", nullable=False)  # Sedentario, Ligero, Moderado, Intenso
    digestive_symptoms = Column(Text, nullable=True)  # Estreñimiento, acidez, reflujo, distensión, etc.
    food_preferences = Column(Text, nullable=True)  # Alimentos favoritos, rechazados, dieta omnívora/vegana, etc.
    goal = Column(String(200), default="Pérdida de grasa", nullable=False)  # Pérdida de grasa, Masa muscular, etc.

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    patient = relationship("User", foreign_keys=[patient_id])
    tenant = relationship("Tenant")


class ClinicalRecord(Base):
    __tablename__ = "clinical_records"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    patient_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    nutritionist_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)

    diagnosis = Column(Text, nullable=False)  # Diagnóstico clínico nutricional
    evolution_notes = Column(Text, nullable=True)  # Notas de consulta y evolución
    clinical_goals = Column(Text, nullable=True)  # Metas clínicas trazadas por el profesional

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
