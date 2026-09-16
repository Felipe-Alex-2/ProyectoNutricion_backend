import hashlib
import json
import os
from datetime import datetime, timezone, timedelta
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

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "backups")


class BackupService:

    @staticmethod
    def _ensure_backup_dir() -> str:
        os.makedirs(BACKUP_DIR, exist_ok=True)
        return BACKUP_DIR

    @classmethod
    def get_or_create_settings(cls, db: Session) -> BackupSetting:
        setting = db.query(BackupSetting).first()
        if not setting:
            setting = BackupSetting(
                auto_backup_enabled=False,
                frequency_hours=24,
                retention_days=30,
            )
            db.add(setting)
            db.commit()
            db.refresh(setting)
        return setting

    @classmethod
    def update_settings(cls, db: Session, data: BackupSettingUpdate) -> BackupSetting:
        setting = cls.get_or_create_settings(db)
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
    def create_backup(
        cls,
        db: Session,
        backup_type: str = "MANUAL",
        user_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Genera un snapshot completo del sistema en JSON con checksum SHA-256.
        """
        cls._ensure_backup_dir()

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"backup_nutrisalud_{backup_type.lower()}_{timestamp_str}.json"
        filepath = os.path.join(BACKUP_DIR, filename)

        snapshot_data = {
            "version": "1.0.0",
            "system": "NutriSalud Multi-Tenant",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "backup_type": backup_type,
            "created_by": user_name or "Sistema",
            "tables": {},
        }

        # Tablas a respaldar en orden de dependencias
        def model_to_dict(obj):
            d = {}
            for col in obj.__table__.columns:
                val = getattr(obj, col.name)
                if isinstance(val, datetime):
                    val = val.isoformat()
                d[col.name] = val
            return d

        models_map = [
            ("tenants", Tenant),
            ("roles", Role),
            ("permissions", Permission),
            ("role_permissions", RolePermission),
            ("users", User),
            ("patient_links", PatientNutritionistLink),
            ("recipes", Recipe),
            ("recipe_assignments", RecipeAssignment),
            ("patient_anamnesis", PatientAnamnesis),
            ("clinical_records", ClinicalRecord),
            ("subscriptions", Subscription),
            ("payments", Payment),
            ("appointments", Appointment),
            ("notifications", Notification),
            ("activity_logs", ActivityLog),
        ]

        table_counts = {}
        for table_key, model_cls in models_map:
            records = db.query(model_cls).all()
            snapshot_data["tables"][table_key] = [model_to_dict(r) for r in records]
            table_counts[table_key] = len(records)

        snapshot_data["record_counts"] = table_counts
        snapshot_data["total_records"] = sum(table_counts.values())

        # Serializar y calcular checksum
        json_bytes = json.dumps(snapshot_data, indent=2, ensure_ascii=False).encode("utf-8")
        checksum = hashlib.sha256(json_bytes).hexdigest()
        snapshot_data["checksum_sha256"] = checksum

        with open(filepath, "wb") as f:
            f.write(json.dumps(snapshot_data, indent=2, ensure_ascii=False).encode("utf-8"))

        file_size = os.path.getsize(filepath)

        # Registrar en BackupLog
        log_entry = BackupLog(
            filename=filename,
            file_size_bytes=file_size,
            checksum=checksum,
            backup_type=backup_type,
            status="SUCCESS",
            details=f"Snapshot con {snapshot_data['total_records']} registros respaldados exitosamente.",
        )
        db.add(log_entry)

        # Actualizar last_backup_at en settings
        settings = cls.get_or_create_settings(db)
        settings.last_backup_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(log_entry)

        return {
            "id": log_entry.id,
            "filename": filename,
            "file_size_bytes": file_size,
            "checksum": checksum,
            "total_records": snapshot_data["total_records"],
            "table_counts": table_counts,
            "created_at": log_entry.created_at,
            "filepath": filepath,
        }

    @classmethod
    def list_backups(cls, db: Session, limit: int = 50) -> List[BackupLog]:
        return db.query(BackupLog).order_by(BackupLog.created_at.desc()).limit(limit).all()

    @classmethod
    def get_backup_filepath(cls, filename: str) -> Optional[str]:
        cls._ensure_backup_dir()
        safe_name = os.path.basename(filename)
        path = os.path.join(BACKUP_DIR, safe_name)
        if os.path.exists(path):
            return path
        return None

    @classmethod
    def check_and_run_auto_backup(cls, db: Session) -> Optional[Dict[str, Any]]:
        """Verifica si corresponde ejecutar una copia automática según la frecuencia configurada."""
        settings = cls.get_or_create_settings(db)
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

        # Ejecutar backup automático
        return cls.create_backup(db, backup_type="AUTOMATICO", user_name="Cron Automático")

    @classmethod
    def restore_backup_from_json(cls, db: Session, backup_content: Dict[str, Any]) -> BackupRestoreResponse:
        """
        Restaura datos desde un snapshot JSON verificado.
        """
        tables = backup_content.get("tables", {})
        if not tables:
            raise ValueError("El archivo no contiene una estructura válida de respaldo ('tables').")

        # Parsear fechas
        def parse_date(val):
            if val and isinstance(val, str):
                try:
                    return datetime.fromisoformat(val)
                except Exception:
                    pass
            return val

        restored_records = 0
        restored_tables = 0

        # Para cada tabla soportada, sincronizar o insertar registros
        models_order = [
            ("tenants", Tenant),
            ("roles", Role),
            ("permissions", Permission),
            ("role_permissions", RolePermission),
            ("users", User),
            ("patient_links", PatientNutritionistLink),
            ("recipes", Recipe),
            ("recipe_assignments", RecipeAssignment),
            ("patient_anamnesis", PatientAnamnesis),
            ("clinical_records", ClinicalRecord),
            ("subscriptions", Subscription),
            ("payments", Payment),
            ("appointments", Appointment),
            ("notifications", Notification),
            ("activity_logs", ActivityLog),
        ]

        for table_name, model_cls in models_order:
            rows = tables.get(table_name, [])
            if not rows:
                continue

            restored_tables += 1
            for row in rows:
                # Convertir fechas
                cleaned_row = {}
                for k, v in row.items():
                    if k in ["created_at", "updated_at", "assigned_at", "linked_at", "scheduled_at", "last_backup_at"]:
                        cleaned_row[k] = parse_date(v)
                    else:
                        cleaned_row[k] = v

                # Verificar si ya existe por ID (o clave primaria)
                pk_val = cleaned_row.get("id")
                if pk_val:
                    existing = db.query(model_cls).filter(getattr(model_cls, "id") == pk_val).first()
                    if existing:
                        for field, val in cleaned_row.items():
                            if field != "id":
                                setattr(existing, field, val)
                    else:
                        obj = model_cls(**cleaned_row)
                        db.add(obj)
                else:
                    obj = model_cls(**cleaned_row)
                    db.add(obj)

                restored_records += 1

        db.commit()

        return BackupRestoreResponse(
            success=True,
            message=f"Restauración completada con éxito. Se procesaron {restored_tables} tablas y {restored_records} registros.",
            tables_restored=restored_tables,
            records_restored=restored_records,
        )
