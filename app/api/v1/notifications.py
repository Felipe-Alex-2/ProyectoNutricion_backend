from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationCountOut
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=List[NotificationOut])
def get_my_notifications(
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene el listado de notificaciones para el usuario en sesión.
    """
    return NotificationService.get_user_notifications(db=db, user_id=current_user.id, limit=limit)


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
