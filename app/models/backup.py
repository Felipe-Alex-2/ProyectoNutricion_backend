import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from app.database import Base


class BackupSetting(Base):
    __tablename__ = "backup_settings"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    auto_backup_enabled = Column(Boolean, default=False, nullable=False)
    frequency_hours = Column(Integer, default=24, nullable=False)  # 6, 12, 24 (diario), 168 (semanal)
    last_backup_at = Column(DateTime, nullable=True)
    retention_days = Column(Integer, default=30, nullable=False)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class BackupLog(Base):
    __tablename__ = "backup_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    filename = Column(String(255), nullable=False)
    file_size_bytes = Column(Integer, default=0, nullable=False)
    checksum = Column(String(64), nullable=True)  # SHA-256
    backup_type = Column(String(50), default="MANUAL", nullable=False)  # MANUAL o AUTOMATICO
    status = Column(String(50), default="SUCCESS", nullable=False)  # SUCCESS, FAILED
    details = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
