"""Server-side resource policies shared by API routers."""
from sqlalchemy.orm import Session
from app.core.exceptions import ForbiddenException, NotFoundException
from app.models.user import User
from app.models.patient_link import PatientNutritionistLink

STAFF_ROLES = {"SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA"}
ADMIN_ROLES = {"SUPERADMIN", "ADMIN_ORGANIZATION"}
VALID_ROLES = STAFF_ROLES | {"CLIENTE"}


def require_role(user: User, roles: set[str]) -> None:
    if user.role_id not in roles:
        raise ForbiddenException("No tienes permisos para realizar esta operación.")


def require_tenant(user: User, tenant_id: str | None) -> None:
    if user.role_id == "SUPERADMIN":
        return
    if not user.tenant_id or not tenant_id or user.tenant_id != tenant_id:
        raise ForbiddenException("El recurso no pertenece a tu organización.")


def require_user_management(actor: User, target: User | None = None) -> None:
    require_role(actor, ADMIN_ROLES)
    if target is not None:
        require_tenant(actor, target.tenant_id)
        if actor.role_id != "SUPERADMIN" and target.role_id == "SUPERADMIN":
            raise ForbiddenException("No puedes gestionar un administrador global.")


def require_patient_access(db: Session, actor: User, patient_id: str, *, allow_self: bool = False) -> User:
    patient = db.get(User, patient_id)
    if patient is None:
        raise NotFoundException("Paciente no encontrado.")
    if allow_self and actor.id == patient.id:
        return patient
    require_role(actor, STAFF_ROLES)
    if actor.role_id == "SUPERADMIN":
        return patient
    require_tenant(actor, patient.tenant_id)
    if actor.role_id == "NUTRICIONISTA":
        linked = db.query(PatientNutritionistLink.id).filter(
            PatientNutritionistLink.patient_id == patient.id,
            PatientNutritionistLink.nutritionist_id == actor.id,
            PatientNutritionistLink.status == "LINKED",
        ).first()
        if not linked:
            raise ForbiddenException("El paciente no está vinculado a tu cuenta.")
    return patient
