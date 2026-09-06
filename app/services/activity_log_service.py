from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.activity_log import ActivityLog
from app.models.user import User
from app.schemas.activity_log import ActivityLogCreate


class ActivityLogService:
    @staticmethod
    def log(
        db: Session,
        user: Optional[User],
        data: ActivityLogCreate,
    ) -> ActivityLog:
        log_entry = ActivityLog(
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_name=user.full_name if user else "Invitado / Sistema",
            action=data.action.upper(),
            description=data.description,
            category=data.category or "SISTEMA",
            ip_address=data.ip_address,
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        return log_entry

    @staticmethod
    def list_logs(
        db: Session,
        user: User,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[ActivityLog]:
        # Cada cuenta solo consulta y visualiza estrictamente sus propios registros
        query = db.query(ActivityLog).filter(ActivityLog.user_id == user.id)

        if category:
            query = query.filter(ActivityLog.category == category)

        return query.order_by(ActivityLog.created_at.desc()).limit(limit).all()

    @staticmethod
    def clear_user_logs(db: Session, user: User) -> int:
        """Borra todos los registros de bitácora del usuario especificado."""
        deleted = db.query(ActivityLog).filter(ActivityLog.user_id == user.id).delete(synchronize_session=False)
        db.commit()
        return deleted

