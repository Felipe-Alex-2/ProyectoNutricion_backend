from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import (
    NotificationOut,
    NotificationCountOut,
    NotificationCreate,
    BroadcastNotificationCreate,
    BroadcastNotificationOut,
)
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationOut])
def get_my_notifications(
    limit: int = Query(50, ge=1, le=100),
    tenant_id: Optional[str] = Query(None, description="Filtrar por organización (ADMIN_SAAS)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el listado de notificaciones para el usuario en sesión.
    """
    effective_tenant = tenant_id if current_user.role_id == "ADMIN_SAAS" else current_user.tenant_id
    return NotificationService.get_user_notifications(db=db, user_id=current_user.id, limit=limit, tenant_id=effective_tenant)


@router.get("/unread-count", response_model=NotificationCountOut)
def get_unread_notification_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene la cantidad de notificaciones no leídas para mostrar en el badge/globito numérico.
    """
    count = NotificationService.get_unread_count(db=db, user_id=current_user.id)
    return NotificationCountOut(unread_count=count)


@router.post("/send", response_model=NotificationOut)
def send_notification(
    payload: NotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envía una notificación a un usuario (ej. seguimiento de dieta, cita, etc.).
    Si el emisor no es ADMIN_SAAS, valida que el destinatario pertenezca a su misma clínica.
    """
    if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
        target_user = db.query(User).filter(User.id == payload.user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="Usuario destinatario no encontrado.")
        if target_user.tenant_id != current_user.tenant_id:
            raise HTTPException(status_code=403, detail="No puedes enviar notificaciones a pacientes de otra clínica.")

    return NotificationService.create_notification(
        db=db,
        user_id=payload.user_id,
        title=payload.title,
        message=payload.message,
        type=payload.type,
        reference_id=payload.reference_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/broadcast-tenant", response_model=BroadcastNotificationOut)
def broadcast_tenant_notifications(
    payload: BroadcastNotificationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Envía una notificación a todos los pacientes (o grupo seleccionado) del tenant.
    Aparecerá en el Centro de Notificaciones de la aplicación móvil de los clientes.
    """
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para emitir notificaciones a pacientes.",
        )

    q = db.query(User).filter(User.role_id == "CLIENTE", User.is_active == True)
    if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
        q = q.filter(User.tenant_id == current_user.tenant_id)

    if payload.patient_ids and len(payload.patient_ids) > 0:
        q = q.filter(User.id.in_(payload.patient_ids))

    patients = q.all()
    sent_count = 0
    tenant_id = current_user.tenant_id

    for p in patients:
        NotificationService.create_notification(
            db=db,
            user_id=p.id,
            title=payload.title,
            message=payload.message,
            type=payload.type,
            reference_id=payload.reference_id,
            tenant_id=tenant_id,
        )
        sent_count += 1

    return BroadcastNotificationOut(
        sent_count=sent_count,
        message=f"Se enviaron con éxito {sent_count} notificaciones a los pacientes de la clínica.",
    )


@router.patch("/{notification_id}/read", response_model=NotificationOut)
def mark_notification_read(
    notification_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marca una notificación individual como leída.
    """
    notif = NotificationService.mark_as_read(db=db, notification_id=notification_id, user_id=current_user.id)
    if not notif:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificación no encontrada",
        )
    return notif


@router.patch("/read-all")
def mark_all_notifications_read(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Marca todas las notificaciones del usuario como leídas.
    """
    updated_count = NotificationService.mark_all_as_read(db=db, user_id=current_user.id)
    return {"message": "Todas las notificaciones han sido marcadas como leídas", "updated_count": updated_count}
