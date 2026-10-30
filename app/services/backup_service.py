import hashlib
import json
import os
from datetime import datetime, timezone, timedelta, date
import base64
from uuid import uuid4
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, and_, DateTime, Date
from app.config import settings as app_settings
from app.database import Base
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.rbac import Role, Permission, RolePermission
from app.models.user import User
from app.models.patient_link import PatientNutritionistLink
from app.models.activity_log import ActivityLog
from app.models.recipe import Recipe, RecipeAssignment
from app.models.clinical import PatientAnamnesis, ClinicalRecord
from app.models.subscription import Subscription
from app.models.payment import Payment
from app.models.appointment import Appointment
from app.models.notification import Notification
from app.models.backup import BackupSetting, BackupLog
from app.schemas.backup import BackupSettingUpdate, BackupRestoreResponse

BACKUP_DIR = app_settings.BACKUP_DIR


class BackupService:

    @staticmethod
    def _ensure_backup_dir() -> str:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        return BACKUP_DIR

    @classmethod
    def get_or_create_settings(cls, db: Session, tenant_id: Optional[str] = None) -> BackupSetting:
        q = db.query(BackupSetting)
        if tenant_id:
            q = q.filter(BackupSetting.tenant_id == tenant_id)
        else:
            q = q.filter(BackupSetting.tenant_id == None)
        setting = q.first()
        if not setting:
            setting = BackupSetting(
                tenant_id=tenant_id,
                auto_backup_enabled=False,
                frequency_hours=24,
                retention_days=30,
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    @classmethod
    def update_settings(cls, db: Session, data: BackupSettingUpdate, tenant_id: Optional[str] = None) -> BackupSetting:
        setting = cls.get_or_create_settings(db, tenant_id=tenant_id)
        if data.auto_backup_enabled is not None:
            setting.auto_backup_enabled = data.auto_backup_enabled
        if data.frequency_hours is not None:
            setting.frequency_hours = data.frequency_hours
        if data.retention_days is not None:
            setting.retention_days = data.retention_days

        db.commit()
        db.refresh(setting)
        return setting

    @classmethod
    def create_backup(cls, db, backup_type="MANUAL", user_name=None, tenant_id=None):
        from app.services.backup_recovery_service import TABLES, canonical
        from app.models.generated_report import GeneratedReport
        from app.models.ai_nutrition import NutritionalPlan
        if not tenant_id or not db.get(Tenant, tenant_id):
            raise ValueError("Selecciona una empresa para crear su respaldo operativo.")
        cls._ensure_backup_dir()
        models = {"payments": Payment, "recipes": Recipe, "recipe_assignments": RecipeAssignment, "nutritional_plans": NutritionalPlan, "appointments": Appointment, "activity_logs": ActivityLog, "generated_reports": GeneratedReport}
        tables = {}
        recipe_ids = [r[0] for r in db.query(Recipe.id).filter(Recipe.tenant_id == tenant_id).all()]
        for name, model in models.items():
            query = db.query(model)
            if name == 'recipe_assignments': query = query.filter(RecipeAssignment.recipe_id.in_(recipe_ids))
            else: query = query.filter(model.tenant_id == tenant_id)
            if name in {'payments', 'appointments'}: query = query.filter(model.status == 'COMPLETED')
            if name == 'activity_logs':
                from app.services.audit_policy import is_mutation
                records = [r for r in query.all() if is_mutation(r.action)]
            else: records = query.all()
            tables[name] = [{c.name: getattr(r, c.name) for c in model.__table__.columns if c.name != 'ip_address'} for r in records]
        snapshot = {"format":"NUTRISALUD_OPERATIONAL_BACKUP", "version":2, "tenant_id":tenant_id, "created_at":datetime.now(timezone.utc).isoformat(), "tables":tables}
        payload = canonical(snapshot).encode()
        if len(payload) > 32*1024*1024: raise ValueError('El respaldo supera 32 MB. Reduce el volumen antes de exportarlo.')
        envelope = json.dumps({"format":"nutrisalud-encrypted-v2", "ciphertext":cls._cipher().encrypt(payload).decode('ascii')}).encode()
        if len(envelope) > 32*1024*1024: raise ValueError('El archivo cifrado supera 32 MB.')
        checksum = hashlib.sha256(envelope).hexdigest()
        filename = f"backup_empresa_{tenant_id}_{uuid4().hex}.json"
        filepath = os.path.join(BACKUP_DIR, filename)
        temporary = filepath + '.tmp'
        try:
            with open(temporary, 'wb') as stream: stream.write(envelope)
            os.replace(temporary, filepath)
        finally:
            if os.path.exists(temporary): os.remove(temporary)
        counts = {name:len(rows) for name,rows in tables.items()}
        total = sum(counts.values())
        setting = cls.get_or_create_settings(db, tenant_id)
        log = BackupLog(tenant_id=tenant_id, filename=filename, file_size_bytes=len(envelope), checksum=checksum, backup_type=backup_type, status='SUCCESS', details=f'Respaldo operativo: {total} registros. '+json.dumps(counts))
        db.add(log); setting.last_backup_at = datetime.now(timezone.utc); db.commit(); db.refresh(log)
        return {"id":log.id,"tenant_id":tenant_id,"filename":filename,"file_size_bytes":len(envelope),"checksum":checksum,"total_records":total,"table_counts":counts,"created_at":log.created_at,"filepath":filepath}

    @classmethod
    def list_backups(cls, db: Session, tenant_id: Optional[str] = None, limit: int = 50) -> List[BackupLog]:
        q = db.query(BackupLog)
        if tenant_id:
            q = q.filter(BackupLog.tenant_id == tenant_id)
        return q.order_by(BackupLog.created_at.desc()).limit(limit).all()

    @classmethod
    def get_backup_filepath(cls, filename: str) -> Optional[str]:
        cls._ensure_backup_dir()
        safe_name = os.path.basename(filename)
        path = os.path.join(BACKUP_DIR, safe_name)
        if os.path.exists(path):
            return path
        return None

    @classmethod
    def check_and_run_auto_backup(cls, db: Session, tenant_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Verifica si corresponde ejecutar una copia automática según la frecuencia configurada."""
        settings = cls.get_or_create_settings(db, tenant_id=tenant_id)
        if not settings.auto_backup_enabled:
            return None

        now = datetime.now(timezone.utc)
        if settings.last_backup_at:
            last = settings.last_backup_at
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            delta = now - last
            if delta < timedelta(hours=settings.frequency_hours):
                return None  # Aún no le toca

        # Ejecutar backup automático para este tenant
        return cls.create_backup(db, backup_type="AUTOMATICO", user_name="Cron Automático", tenant_id=tenant_id)

    @staticmethod
    def _cipher():
        # Dedicated backup keys survive JWT key rotations. Development fallback only.
        secret = app_settings.BACKUP_ENCRYPTION_KEY or app_settings.SECRET_KEY
        key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
        return Fernet(key)

    @classmethod
    def restore_backup_from_json(cls, db, backup_content, tenant_id=None):
        raise ValueError("Analiza el respaldo y confirma con tu contraseña antes de restaurar.")
