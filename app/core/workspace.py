"""Request-local company/branch boundary, independent from account membership."""
from dataclasses import dataclass
from sqlalchemy import event, and_, or_, select, inspect, false
from sqlalchemy.orm import Session, with_loader_criteria
from app.core.exceptions import BadRequestException, ForbiddenException


@dataclass(frozen=True)
class Workspace:
    user_id: str
    tenant_id: str | None
    branch_id: str | None
    staff: bool
    global_view: bool = False


def selection(db, user, company=None, branch=None, *, explicit=False):
    from app.models.company import Branch
    from app.models.tenant import Tenant
    root = user.role_id == 'SUPERADMIN'
    staff = user.role_id != 'CLIENTE'
    if not root:
        if company and company != user.tenant_id:
            raise ForbiddenException('Solo puedes trabajar en tu empresa.')
        company = user.tenant_id
    if not staff:
        if explicit: raise ForbiddenException('El cliente conserva la empresa y sucursal de su registro.')
        return Workspace(user.id, user.tenant_id, user.branch_id, False)
    if not explicit:
        company = user.workspace_tenant_id if root else user.tenant_id
        branch = user.workspace_branch_id or (user.branch_id if not root else None)
    if not company:
        if branch: raise BadRequestException('Selecciona primero una empresa.')
        return Workspace(user.id, None, None, True, root)
    tenant = db.get(Tenant, company)
    if not tenant or not tenant.is_active: raise ForbiddenException('La empresa no está activa.')
    if branch:
        item = db.get(Branch, branch)
        if not item or not item.is_active or item.tenant_id != company:
            raise ForbiddenException('La sucursal no pertenece a la empresa o está inactiva.')
    elif not root:
        choices = db.query(Branch).filter_by(tenant_id=company, is_active=True).all()
        if len(choices) == 1: branch = choices[0].id
        elif choices: raise BadRequestException('Selecciona una sucursal para trabajar.')
        # Empty legacy companies remain readable until their branches are configured.
    return Workspace(user.id, company, branch, True)


def current(db):
    return db.info.get('workspace')


@event.listens_for(Session, 'do_orm_execute')
def scope_queries(state):
    scope = current(state.session)
    if not scope or not scope.staff or scope.global_view or state.is_column_load:
        return
    from app.database import Base
    from app.models.user import User
    from app.models.workspace import WorkspaceOwned
    for mapper in Base.registry.mappers:
        model = mapper.class_
        if issubclass(model, WorkspaceOwned):
            condition = model.tenant_id == scope.tenant_id if scope.tenant_id else false()
            if scope.branch_id: condition = and_(condition, model.branch_id == scope.branch_id)
        elif model is User:
            condition = model.tenant_id == scope.tenant_id if scope.tenant_id else false()
            if scope.branch_id: condition = and_(condition, model.branch_id == scope.branch_id)
            condition = or_(model.id == scope.user_id, condition)
        else:
            continue
        state.statement = state.statement.options(with_loader_criteria(model, condition, include_aliases=True))


def _owner(db, user_id):
    from app.models.user import User
    return db.execute(select(User.__table__.c.tenant_id, User.__table__.c.branch_id).where(User.__table__.c.id == user_id)).first() if user_id else None


@event.listens_for(Session, 'before_flush')
def attribute_and_check_writes(db, flush_context, instances):
    scope = current(db)
    from app.models.workspace import WorkspaceOwned
    from app.models.user import User
    from app.models.company import Branch
    if scope is None:
        # Registration, payment callbacks and scheduled tasks derive ownership from
        # their actual patient/recipient, never from a process-wide active user.
        for obj in list(db.new):
            if not isinstance(obj, WorkspaceOwned): continue
            owner = _owner(db, getattr(obj, 'patient_id', None) or getattr(obj, 'user_id', None))
            if owner:
                if not obj.tenant_id: obj.tenant_id = owner.tenant_id
                if not obj.branch_id and owner.tenant_id == obj.tenant_id: obj.branch_id = owner.branch_id
        return
    for obj in list(db.new) + list(db.dirty) + list(db.deleted):
        if isinstance(obj, User):
            if obj.id == scope.user_id: continue
            if obj in db.new and scope.tenant_id:
                if obj.tenant_id and obj.tenant_id != scope.tenant_id: raise ForbiddenException('La cuenta pertenece a otra empresa.')
                obj.tenant_id = scope.tenant_id
                if scope.branch_id: obj.branch_id = scope.branch_id
            if scope.tenant_id and obj.tenant_id != scope.tenant_id: raise ForbiddenException('La cuenta pertenece a otra empresa.')
            if scope.branch_id and obj.branch_id != scope.branch_id: raise ForbiddenException('La cuenta pertenece a otra sucursal.')
            continue
        if not isinstance(obj, WorkspaceOwned): continue
        if scope.staff and not scope.global_view and not scope.tenant_id:
            raise ForbiddenException('Tu cuenta necesita una empresa y sucursal asignadas.')
        if obj in db.new:
            owner_id = getattr(obj, 'patient_id', None) or getattr(obj, 'user_id', None)
            owner = _owner(db, owner_id)
            if scope.staff and scope.tenant_id:
                if obj.tenant_id and obj.tenant_id != scope.tenant_id: raise ForbiddenException('El registro pertenece a otra empresa.')
                obj.tenant_id = scope.tenant_id
            elif not obj.tenant_id and owner:
                obj.tenant_id = owner.tenant_id
            if scope.staff and scope.branch_id:
                if obj.branch_id and obj.branch_id != scope.branch_id: raise ForbiddenException('El registro pertenece a otra sucursal.')
                if owner and owner_id != scope.user_id and owner.branch_id and owner.branch_id != scope.branch_id:
                    raise ForbiddenException('El paciente o destinatario pertenece a otra sucursal.')
                obj.branch_id = scope.branch_id
            elif not obj.branch_id and owner and owner.tenant_id == obj.tenant_id:
                obj.branch_id = owner.branch_id
            if not obj.branch_id and obj.tenant_id:
                branches = db.execute(select(Branch.__table__.c.id).where(Branch.__table__.c.tenant_id == obj.tenant_id, Branch.__table__.c.is_active.is_(True))).scalars().all()
                if len(branches) == 1: obj.branch_id = branches[0]
                elif branches and obj.__tablename__ not in {'activity_logs','generated_reports','backup_logs','backup_settings'}:
                    raise BadRequestException('Selecciona una sucursal concreta antes de guardar.')
            if scope.global_view and not obj.tenant_id and obj.__tablename__ not in {'activity_logs','generated_reports','backup_logs','backup_settings'}:
                raise BadRequestException('Selecciona una empresa y sucursal para registrar operaciones.')
            if obj.__tablename__ == 'recipe_assignments':
                from app.models.recipe import Recipe
                parent = db.execute(select(Recipe.__table__.c.tenant_id, Recipe.__table__.c.branch_id).where(Recipe.__table__.c.id == obj.recipe_id)).first()
                if parent and (parent.tenant_id != obj.tenant_id or parent.branch_id != obj.branch_id):
                    raise ForbiddenException('La receta y el paciente deben pertenecer a la misma sucursal.')
            if obj.branch_id:
                branch_company = db.execute(select(Branch.__table__.c.tenant_id).where(Branch.__table__.c.id == obj.branch_id)).scalar_one_or_none()
                if branch_company != obj.tenant_id: raise ForbiddenException('La sucursal del registro no pertenece a su empresa.')
        else:
            for field in ('tenant_id', 'branch_id'):
                if inspect(obj).attrs[field].history.has_changes():
                    raise ForbiddenException('La empresa y sucursal de una operación guardada no se pueden trasladar.')
        if scope.staff and scope.tenant_id and obj.tenant_id != scope.tenant_id: raise ForbiddenException('El registro pertenece a otra empresa.')
        if scope.staff and scope.branch_id and obj.branch_id != scope.branch_id: raise ForbiddenException('El registro pertenece a otra sucursal.')
