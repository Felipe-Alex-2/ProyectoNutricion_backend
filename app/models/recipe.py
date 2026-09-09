import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class Recipe(Base):
    __tablename__ = "recipes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    tenant_id = Column(String(36), ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True)
    created_by = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(200), nullable=False, index=True)
    description = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)

    # Macronutrientes por porción
    calories = Column(Float, default=0.0, nullable=False)
    protein = Column(Float, default=0.0, nullable=False)
    carbohydrates = Column(Float, default=0.0, nullable=False)
    fats = Column(Float, default=0.0, nullable=False)
    fiber = Column(Float, default=0.0, nullable=False)
    sodium = Column(Float, default=0.0, nullable=True)

    # Tiempos y dificultad
    servings = Column(Integer, default=1, nullable=False)
    prep_time_minutes = Column(Integer, default=15, nullable=False)
    cook_time_minutes = Column(Integer, default=15, nullable=False)
    difficulty = Column(String(50), default="Fácil", nullable=False)  # Fácil, Media, Difícil
    category = Column(String(50), default="Almuerzo", nullable=False)  # Desayuno, Almuerzo, Cena, Snack, etc.

    # Ingredientes e instrucciones (almacenados en texto estructurado o JSON)
    ingredients = Column(Text, nullable=False)
    instructions = Column(Text, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relaciones
    tenant = relationship("Tenant")
    creator = relationship("User", foreign_keys=[created_by])
