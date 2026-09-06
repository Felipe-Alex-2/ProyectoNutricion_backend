from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.activity_log import ActivityLogCreate, ActivityLogResponse
from app.services.activity_log_service import ActivityLogService

router = APIRouter(prefix="/activity-logs", tags=["Bitácora de Actividades"])


@router.get("", response_model=List[ActivityLogResponse])
def list_logs(
    category: Optional[str] = Query(None),
    limit: int = Query(100, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return ActivityLogService.list_logs(db, user=current_user, category=category, limit=limit)


@router.post("", response_model=ActivityLogResponse, status_code=status.HTTP_201_CREATED)
def record_log(
    data: ActivityLogCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not data.ip_address:
        data.ip_address = request.client.host if request.client else None
    return ActivityLogService.log(db, user=current_user, data=data)


@router.delete("", status_code=status.HTTP_200_OK)
def clear_my_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    deleted = ActivityLogService.clear_user_logs(db, user=current_user)
    return {"message": "Registros de bitácora eliminados exitosamente", "deleted": deleted}

