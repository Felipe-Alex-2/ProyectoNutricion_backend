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
    def create_backup(
        cls,
        db: Session,
        backup_type: str = "MANUAL",
        user_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Genera un snapshot del sistema o exclusivo del tenant en JSON con checksum SHA-256.
        """
        cls._ensure_backup_dir()

        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        prefix = f"backup_tenant_{tenant_id[:8]}" if tenant_id else "backup_nutrisalud_global"
        filename = f"{prefix}_{backup_type.lower()}_{timestamp_str}.json"
        filepath = os.path.join(BACKUP_DIR, filename)

        snapshot_data = {
            "version": "1.0.0",
            "system": "NutriSalud Multi-Tenant",
            "tenant_id": tenant_id,
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

        table_counts = {}

        if tenant_id:
            # Respaldo exclusivo del Tenant
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            snapshot_data["tables"]["tenants"] = [model_to_dict(tenant)] if tenant else []
            table_counts["tenants"] = len(snapshot_data["tables"]["tenants"])

            # Roles y permisos (catálogo base)
            roles = db.query(Role).all()
            snapshot_data["tables"]["roles"] = [model_to_dict(r) for r in roles]
            table_counts["roles"] = len(roles)

            perms = db.query(Permission).all()
            snapshot_data["tables"]["permissions"] = [model_to_dict(p) for p in perms]
            table_counts["permissions"] = len(perms)

            r_perms = db.query(RolePermission).all()
            snapshot_data["tables"]["role_permissions"] = [model_to_dict(rp) for rp in r_perms]
            table_counts["role_permissions"] = len(r_perms)

            # Usuarios del tenant
            users = db.query(User).filter(User.tenant_id == tenant_id).all()
            snapshot_data["tables"]["users"] = [model_to_dict(u) for u in users]
            table_counts["users"] = len(users)
            tenant_user_ids = [u.id for u in users]

            # Links
            links = db.query(PatientNutritionistLink).filter(PatientNutritionistLink.patient_id.in_(tenant_user_ids)).all()
            snapshot_data["tables"]["patient_links"] = [model_to_dict(l) for l in links]
            table_counts["patient_links"] = len(links)

            # Recetas del tenant
            recipes = db.query(Recipe).filter(Recipe.tenant_id == tenant_id).all()
            snapshot_data["tables"]["recipes"] = [model_to_dict(r) for r in recipes]
            table_counts["recipes"] = len(recipes)
            recipe_ids = [r.id for r in recipes]

            # Asignaciones de recetas del tenant
            r_assign = db.query(RecipeAssignment).filter(
                (RecipeAssignment.recipe_id.in_(recipe_ids)) | (RecipeAssignment.patient_id.in_(tenant_user_ids))
            ).all()
            snapshot_data["tables"]["recipe_assignments"] = [model_to_dict(ra) for ra in r_assign]
            table_counts["recipe_assignments"] = len(r_assign)

            # Anamnesis de pacientes del tenant
            anam = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id.in_(tenant_user_ids)).all()
            snapshot_data["tables"]["patient_anamnesis"] = [model_to_dict(a) for a in anam]
            table_counts["patient_anamnesis"] = len(anam)

            # Fichas clínicas del tenant
            clinical = db.query(ClinicalRecord).filter(
                (ClinicalRecord.tenant_id == tenant_id) | (ClinicalRecord.patient_id.in_(tenant_user_ids))
            ).all()
            snapshot_data["tables"]["clinical_records"] = [model_to_dict(c) for c in clinical]
            table_counts["clinical_records"] = len(clinical)

            # Suscripciones
            subs = db.query(Subscription).filter(
                (Subscription.tenant_id == tenant_id) | (Subscription.user_id.in_(tenant_user_ids))
            ).all()
            snapshot_data["tables"]["subscriptions"] = [model_to_dict(s) for s in subs]
            table_counts["subscriptions"] = len(subs)

            # Pagos
            pays = db.query(Payment).filter(Payment.tenant_id == tenant_id).all()
            snapshot_data["tables"]["payments"] = [model_to_dict(p) for p in pays]
            table_counts["payments"] = len(pays)

            # Citas
            appts = db.query(Appointment).filter(
                (Appointment.tenant_id == tenant_id) | (Appointment.patient_id.in_(tenant_user_ids))
            ).all()
            snapshot_data["tables"]["appointments"] = [model_to_dict(a) for a in appts]
            table_counts["appointments"] = len(appts)

            # Notificaciones
            notifs = db.query(Notification).filter(
                (Notification.tenant_id == tenant_id) | (Notification.user_id.in_(tenant_user_ids))
            ).all()
            snapshot_data["tables"]["notifications"] = [model_to_dict(n) for n in notifs]
            table_counts["notifications"] = len(notifs)

            # Logs de actividad
            logs = db.query(ActivityLog).filter(ActivityLog.user_id.in_(tenant_user_ids)).all()
            snapshot_data["tables"]["activity_logs"] = [model_to_dict(l) for l in logs]
            table_counts["activity_logs"] = len(logs)

        else:
            # Respaldo Global (ADMIN_SAAS)
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

        # Registrar en BackupLog con tenant_id
        scope_str = f"Tenant {tenant_id[:8]}" if tenant_id else "Global"
        log_entry = BackupLog(
            tenant_id=tenant_id,
            filename=filename,
            file_size_bytes=file_size,
            checksum=checksum,
            backup_type=backup_type,
            status="SUCCESS",
            details=f"Snapshot [{scope_str}] con {snapshot_data['total_records']} registros respaldados exitosamente.",
        )
        db.add(log_entry)

        # Actualizar last_backup_at en settings
        settings = cls.get_or_create_settings(db, tenant_id=tenant_id)
        settings.last_backup_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(log_entry)

        return {
            "id": log_entry.id,
            "tenant_id": tenant_id,
            "filename": filename,
            "file_size_bytes": file_size,
            "checksum": checksum,
            "total_records": snapshot_data["total_records"],
            "table_counts": table_counts,
            "created_at": log_entry.created_at,
            "filepath": filepath,
        }

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

    @classmethod
    def restore_backup_from_json(
        cls,
        db: Session,
        backup_content: Dict[str, Any],
        tenant_id: Optional[str] = None,
    ) -> BackupRestoreResponse:
        """
        Restaura datos desde un snapshot JSON verificado.
        Si se especifica tenant_id, restringe la restauración exclusivamente a los datos del tenant.
        """
        tables = backup_content.get("tables", {})
        if not tables:
            raise ValueError("El archivo no contiene una estructura válida de respaldo ('tables').")

        backup_tenant_id = backup_content.get("tenant_id")
        if tenant_id:
            if backup_tenant_id and backup_tenant_id != tenant_id:
                raise ValueError("El archivo de respaldo pertenece a otra clínica u organización y no puede ser restaurado en este entorno.")

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

        # Tablas restringidas a nivel global si se restaura por tenant
        global_only_tables = {"tenants", "roles", "permissions", "role_permissions"}

        for table_name, model_cls in models_order:
            if tenant_id and table_name in global_only_tables:
                continue

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

                # Si es tenant específico, asegurar aislamiento
                if tenant_id:
                    if hasattr(model_cls, "tenant_id"):
                        cleaned_row["tenant_id"] = tenant_id

                # Verificar si ya existe por ID (o clave primaria)
                pk_val = cleaned_row.get("id")
                if pk_val:
                    existing = db.query(model_cls).filter(getattr(model_cls, "id") == pk_val).first()
                    if existing:
                        # Si es tenant, no sobreescribir si pertenece a otro tenant
                        if tenant_id and hasattr(existing, "tenant_id") and existing.tenant_id and existing.tenant_id != tenant_id:
                            continue
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
