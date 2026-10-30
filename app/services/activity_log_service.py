from typing import List, Optional
from app.services.audit_policy import is_mutation
from app.core.exceptions import BadRequestException
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
        if not is_mutation(data.action): raise BadRequestException('Solo se registran operaciones que modifican datos.')
        log_entry = ActivityLog(
            tenant_id=user.tenant_id if user else None,
            user_id=user.id if user else None,
            user_email=user.email if user else None,
            user_name=user.full_name if user else "Invitado / Sistema",
            action=data.action.upper(),
            description=data.description,
            category=data.category or "SISTEMA",
            ip_address=None,
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
        query = db.query(ActivityLog)
        if user.role_id == 'SUPERADMIN': pass
        elif user.role_id == 'ADMIN_ORGANIZATION':
            from app.core.authorization import require_tenant
            require_tenant(user, user.tenant_id)
            query = query.filter(ActivityLog.tenant_id == user.tenant_id)
        else: query = query.filter(ActivityLog.user_id == user.id)

        if category:
            query = query.filter(ActivityLog.category == category)

        return [row for row in query.order_by(ActivityLog.created_at.desc()).limit(limit).all() if is_mutation(row.action)]

    @staticmethod
    def clear_user_logs(db: Session, user: User) -> int:
        """Borra todos los registros de bitácora del usuario especificado."""
        deleted = db.query(ActivityLog).filter(ActivityLog.user_id == user.id).delete(synchronize_session=False)
        db.commit()
        return deleted

