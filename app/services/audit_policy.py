"""Only business mutations are eligible for the activity log."""
from uuid import uuid4
from sqlalchemy import event, inspect
from sqlalchemy.orm import Session


NON_MUTATION_WORDS = ('NAVEG', 'LOGIN', 'LOGOUT', 'ACCESO', 'VISUAL', 'VERIFIC', 'CAMBIO_TEMA', 'DESBLOQUE')
MUTATION_WORDS = ('CREA', 'REGISTR', 'ACTUALIZ', 'UPDATE', 'EDIT', 'MODIFIC', 'ELIMIN', 'DELETE', 'BORRA', 'DESACTIV', 'ACTIVAD', 'CANCEL', 'CONFIRM', 'ASIGNA', 'VINCUL', 'APROB', 'GUARD', 'RESTAUR', 'BACKUP', 'EXPORT', 'PAGO', 'COBRO', 'ANAMNESIS', 'DIAGNOST', 'SUSCRIP', 'ATENDIDA')


def is_mutation(action):
    value = (action or '').upper()
    return not any(word in value for word in NON_MUTATION_WORDS) and any(word in value for word in MUTATION_WORDS)


@event.listens_for(Session, 'before_flush')
def audit_business_changes(db, flush_context, instances):
    from app.models.activity_log import ActivityLog
    from app.models.user import User
    for log in list(db.new):
        if isinstance(log, ActivityLog):
            log.ip_address = None
            if not is_mutation(log.action): db.expunge(log)
            elif not log.tenant_id and log.user_id:
                with db.no_autoflush:
                    user = db.get(User, log.user_id)
                    log.tenant_id = user.tenant_id if user else None
    actor = db.info.get('audit_actor')
    if actor is None: return
    excluded = {'activity_logs', 'token_blacklist', 'backup_logs', 'backup_settings', 'device_tokens'}
    for state, objects in [('CREADO', list(db.new)), ('ACTUALIZADO', list(db.dirty)), ('ELIMINADO', list(db.deleted))]:
        for obj in objects:
            table = getattr(obj, '__tablename__', '')
            if not table or table in excluded: continue
            if state == 'ACTUALIZADO':
                changed = {attr.key for attr in inspect(obj).attrs if attr.history.has_changes()}
                if not changed or changed <= {'session_version', 'updated_at', 'is_read', 'reminder_sent', 'workspace_tenant_id', 'workspace_branch_id'}: continue
            if hasattr(obj, 'id') and obj.id is None: obj.id = str(uuid4())
            company = getattr(obj, 'tenant_id', None) or (obj.id if table == 'tenants' else actor.tenant_id)
            label = getattr(obj, 'title', None) or getattr(obj, 'name', None) or getattr(obj, 'full_name', None) or getattr(obj, 'id', '')
            action = f'{table.upper()}_{state}'
            if table == 'appointments' and state == 'ACTUALIZADO':
                action = {'CONFIRMED':'CITA_CONFIRMADA','CANCELLED':'CITA_CANCELADA','COMPLETED':'CITA_ATENDIDA'}.get(obj.status, action)
            if table == 'payments' and getattr(obj, 'status', '') == 'COMPLETED' and (state == 'CREADO' or inspect(obj).attrs.status.history.has_changes()): action = 'COBRO_CONFIRMADO'
            from app.core.workspace import current
            scope = current(db)
            db.add(ActivityLog(tenant_id=company or (scope.tenant_id if scope else None), branch_id=(scope.branch_id if scope and scope.branch_id else getattr(obj, 'branch_id', None)), user_id=actor.id, user_email=actor.email, user_name=actor.full_name, action=action, description=f'{action}: {table} · {str(label)[:200]}', category='OPERACIONES'))
