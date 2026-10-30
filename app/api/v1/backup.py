import json
import os
from typing import List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
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
from app.core.authorization import require_role, require_tenant
from starlette.concurrency import run_in_threadpool

router = APIRouter(prefix="/backup", tags=["Copias de Seguridad (Backup)"])


def ensure_backup_access(user: User):
    if user.role_id not in ["SUPERADMIN", "ADMIN_ORGANIZATION"]:
        raise ForbiddenException("No tiene permisos para gestionar copias de seguridad.")
    if user.role_id != "SUPERADMIN":
        require_tenant(user, user.tenant_id)


@router.get("/settings", response_model=BackupSettingResponse)
def get_backup_settings(
    tenant_id: Optional[str] = Query(None, description="ID del tenant a configurar (SUPERADMIN)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    effective_tenant = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else tenant_id
    if not effective_tenant: raise BadRequestException('Selecciona una empresa.')
    return BackupService.get_or_create_settings(db, tenant_id=effective_tenant)


@router.put("/settings", response_model=BackupSettingResponse)
def update_backup_settings(
    data: BackupSettingUpdate,
    tenant_id: Optional[str] = Query(None, description="ID del tenant a configurar (SUPERADMIN)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    effective_tenant = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else tenant_id
    if not effective_tenant: raise BadRequestException('Selecciona una empresa.')
    updated = BackupService.update_settings(db, data, tenant_id=effective_tenant)
    try:
        scope_str = f"Tenant {effective_tenant[:8]}" if effective_tenant else "Global"
        db.add(ActivityLog(
            tenant_id=effective_tenant,
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
    tenant_id: Optional[str] = Query(None, description="ID del tenant para respaldo exclusivo (SUPERADMIN)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    effective_tenant = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else tenant_id
    if not effective_tenant: raise BadRequestException('Selecciona una empresa para respaldar.')
    result = BackupService.create_backup(db, backup_type="MANUAL", user_name=current_user.full_name, tenant_id=effective_tenant)

    try:
        scope_str = f"Tenant {effective_tenant[:8]}" if effective_tenant else "Global"
        db.add(ActivityLog(
            tenant_id=effective_tenant,
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
    tenant_id: Optional[str] = Query(None, description="ID del tenant (SUPERADMIN)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    effective_tenant = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else tenant_id
    return BackupService.list_backups(db, tenant_id=effective_tenant)


@router.get("/download/{filename}")
def download_backup_file(
    filename: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_backup_access(current_user)
    tenant_id = current_user.tenant_id if current_user.role_id != "SUPERADMIN" else None
    if tenant_id:
        log = db.query(BackupLog).filter(BackupLog.filename == filename).first()
        if not log or log.tenant_id != tenant_id:
            raise ForbiddenException("No tiene permisos para descargar el respaldo de otra clínica u organización.")

    filepath = BackupService.get_backup_filepath(filename)
    if not filepath or not os.path.exists(filepath):
        raise NotFoundException(f"El archivo de respaldo '{filename}' no se encuentra disponible.")

    import hashlib
    log = db.query(BackupLog).filter_by(filename=filename).first()
    if not log: raise NotFoundException('Respaldo no registrado.')
    with open(filepath, 'rb') as stream: actual = hashlib.sha256(stream.read()).hexdigest()
    if log.checksum and actual != log.checksum: raise BadRequestException('El respaldo no pasó la verificación de integridad.')
    return FileResponse(
        path=filepath,
        filename=os.path.basename(filepath),
        media_type="application/json",
        headers={"Cache-Control":"private, no-store", "X-Content-Type-Options":"nosniff"},
    )


def resolve_backup_company(user, tenant_id):
    ensure_backup_access(user)
    company = tenant_id if user.role_id == 'SUPERADMIN' else user.tenant_id
    if not company: raise BadRequestException('Selecciona una empresa.')
    if user.role_id != 'SUPERADMIN' and tenant_id and tenant_id != company: raise ForbiddenException('El respaldo pertenece a otra empresa.')
    return company


@router.post('/preview')
async def preview_backup(file: UploadFile = File(...), tenant_id: Optional[str] = Query(None), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.backup_recovery_service import BackupRecoveryService, MAX_BYTES
    company = resolve_backup_company(current_user, tenant_id)
    content = await file.read(MAX_BYTES+1)
    try: return BackupRecoveryService.preview(db, content, company, current_user)
    except ValueError as exc: raise BadRequestException(str(exc))


@router.post('/restore', response_model=BackupRestoreResponse)
async def restore_backup(file: UploadFile = File(...), password: str = Form(...), review_token: str = Form(...), tenant_id: Optional[str] = Query(None), current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.backup_recovery_service import BackupRecoveryService, MAX_BYTES
    company = resolve_backup_company(current_user, tenant_id)
    content = await file.read(MAX_BYTES+1)
    try: return BackupRecoveryService.restore(db, content, company, current_user, review_token, password)
    except ValueError as exc: raise BadRequestException(str(exc))
