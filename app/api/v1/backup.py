import json
import os
from typing import List
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.models.backup import BackupLog
from app.schemas.backup import (
    BackupSettingResponse,
    BackupSettingUpdate,
    BackupLogResponse,
    BackupRestoreResponse,
)
from app.services.backup_service import BackupService
from app.core.exceptions import ForbiddenException, NotFoundException, BadRequestException

router = APIRouter(prefix="/backup", tags=["Copias de Seguridad (Backup)"])


def ensure_backup_access(user: User):
    if user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise ForbiddenException("No tiene permisos para gestionar copias de seguridad.")


@router.get("/settings", response_model=BackupSettingResponse)
def get_backup_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    return BackupService.get_or_create_settings(db, tenant_id=tenant_id)


@router.put("/settings", response_model=BackupSettingResponse)
def update_backup_settings(
    data: BackupSettingUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    updated = BackupService.update_settings(db, data, tenant_id=tenant_id)
    try:
        scope_str = f"Tenant {tenant_id[:8]}" if tenant_id else "Global"
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="BACKUP_CONFIG_ACTUALIZADA",
            description=f"Se actualizó la configuración de copias de seguridad automáticas [{scope_str}]: activo={updated.auto_backup_enabled}, cada {updated.frequency_hours} horas.",
            category="SYSTEM",
        ))
        db.commit()
    except Exception:
        pass
    return updated


@router.post("/export", response_model=BackupLogResponse)
def export_backup_manual(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    result = BackupService.create_backup(db, backup_type="MANUAL", user_name=current_user.full_name, tenant_id=tenant_id)

    try:
        scope_str = f"Tenant {tenant_id[:8]}" if tenant_id else "Global"
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="BACKUP_MANUAL_CREADO",
            description=f"Respaldo manual [{scope_str}] generado con éxito: {result['filename']} ({result['total_records']} registros).",
            category="SYSTEM",
        ))
        db.commit()
    except Exception:
        pass

    log_entry = db.query(BackupLog).filter_by(id=result["id"]).first()
    return log_entry


@router.get("/history", response_model=List[BackupLogResponse])
def get_backup_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    # Ejecutar verificación si corresponde copia automática
    try:
        BackupService.check_and_run_auto_backup(db, tenant_id=tenant_id)
    except Exception:
        pass
    return BackupService.list_backups(db, tenant_id=tenant_id)


@router.get("/download/{filename}")
def download_backup_file(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    if tenant_id:
        log = db.query(BackupLog).filter(BackupLog.filename == filename).first()
        if log and log.tenant_id and log.tenant_id != tenant_id:
            raise ForbiddenException("No tiene permisos para descargar el respaldo de otra clínica u organización.")

    filepath = BackupService.get_backup_filepath(filename)
    if not filepath or not os.path.exists(filepath):
        raise NotFoundException(f"El archivo de respaldo '{filename}' no se encuentra disponible.")

    return FileResponse(
        path=filepath,
        filename=os.path.basename(filepath),
        media_type="application/json",
    )


@router.post("/restore", response_model=BackupRestoreResponse)
async def restore_backup(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "ADMIN_SAAS" else None
    try:
        content_bytes = await file.read()
        json_data = json.loads(content_bytes.decode("utf-8"))
    except Exception as e:
        raise BadRequestException(f"El archivo subido no es un JSON válido: {str(e)}")

    try:
        res = BackupService.restore_backup_from_json(db, json_data, tenant_id=tenant_id)

        scope_str = f"Tenant {tenant_id[:8]}" if tenant_id else "Global"
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="BACKUP_RESTAURADO",
            description=f"Restauración ejecutada [{scope_str}] desde archivo '{file.filename}': {res.records_restored} registros.",
            category="SYSTEM",
        ))
        db.commit()
        return res
    except ValueError as ve:
        raise BadRequestException(str(ve))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error durante la restauración: {str(e)}"
        )
