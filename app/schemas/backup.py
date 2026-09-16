from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class BackupSettingBase(BaseModel):
    auto_backup_enabled: bool = Field(False, description="Activar copias de seguridad automáticas")
    frequency_hours: int = Field(24, ge=1, le=720, description="Frecuencia en horas (ej: 6, 12, 24, 168)")
    retention_days: int = Field(30, ge=1, le=365, description="Días de retención")


class BackupSettingUpdate(BaseModel):
    auto_backup_enabled: Optional[bool] = None
    frequency_hours: Optional[int] = Field(None, ge=1, le=720)
    retention_days: Optional[int] = Field(None, ge=1, le=365)


class BackupSettingResponse(BackupSettingBase):
    id: str
    last_backup_at: Optional[datetime] = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupLogResponse(BaseModel):
    id: str
    filename: str
    file_size_bytes: int
    checksum: Optional[str] = None
    backup_type: str
    status: str
    details: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class BackupRestoreResponse(BaseModel):
    success: bool
    message: str
    tables_restored: int
    records_restored: int
