from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentCancel,
    AppointmentOut,
    NutritionistOut,
)
from app.services.appointment_service import AppointmentService

router = APIRouter(prefix="/appointments", tags=["Appointments"])


@router.post("", response_model=AppointmentOut)
def schedule_appointment(
    body: AppointmentCreate,
    idempotency_key: Optional[str] = Header(None, min_length=1, max_length=128),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Agenda una nueva cita médica/nutricional. Queda en estado PENDING y notifica al especialista.
    """
    return AppointmentService.create_appointment(db=db, current_user=current_user, data=body, idempotency_key=idempotency_key)


@router.get("", response_model=List[AppointmentOut])
def get_appointments(
    status: Optional[str] = Query(None, description="Filtro de estado: PENDING, CONFIRMED, CANCELLED o ALL"),
    tenant_id: Optional[str] = Query(None, description="ID del tenant (solo para administradores)"),
    nutritionist_id: Optional[str] = Query(None, description="Filtrar por nutricionista específico"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Lista las citas asociadas al usuario actual o a la organización/clínica según rol.
    """
    return AppointmentService.list_appointments(
        db=db,
        current_user=current_user,
        status_filter=status,
        tenant_id=tenant_id,
        nutritionist_id=nutritionist_id,
    )


@router.get("/nutritionists", response_model=List[NutritionistOut])
def get_nutritionists(
    tenant_id: Optional[str] = Query(None, description="Filtrar por sucursal o clínica"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Obtiene la lista de nutricionistas disponibles para agendar citas.
    """
    return AppointmentService.get_available_nutritionists(
        db=db, current_user=current_user, tenant_id=tenant_id
    )


@router.post("/{appointment_id}/confirm", response_model=AppointmentOut)
def confirm_appointment(
    appointment_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirma una cita médica/nutricional pendiente y notifica al paciente.
    """
    return AppointmentService.confirm_appointment(
        db=db, appointment_id=appointment_id, current_user=current_user
    )


@router.post("/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_appointment(
    appointment_id: str,
    body: Optional[AppointmentCancel] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancela una cita médica/nutricional, guarda el motivo y notifica a las partes.
    """
    reason = body.cancellation_reason if body else None
    return AppointmentService.cancel_appointment(
        db=db, appointment_id=appointment_id, reason=reason, current_user=current_user
    )


@router.post('/{appointment_id}/complete', response_model=AppointmentOut)
def complete_appointment(appointment_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from app.core.authorization import STAFF_ROLES, require_role, require_tenant
    from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException
    from app.models.appointment import Appointment
    from datetime import datetime, timezone
    require_role(current_user, STAFF_ROLES)
    appointment = db.get(Appointment, appointment_id)
    if not appointment: raise NotFoundException('Cita no encontrada.')
    require_tenant(current_user, appointment.tenant_id)
    if current_user.role_id == 'NUTRICIONISTA' and appointment.nutritionist_id != current_user.id: raise ForbiddenException('La cita pertenece a otro especialista.')
    if appointment.status == 'COMPLETED': return AppointmentService._to_out(appointment)
    if appointment.status != 'CONFIRMED': raise BadRequestException('Solo se puede completar una cita confirmada.')
    if appointment.scheduled_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc): raise BadRequestException('La cita todavía no ocurrió.')
    appointment.status = 'COMPLETED'; appointment.completed_at = datetime.now(timezone.utc)
    db.commit(); db.refresh(appointment)
    return AppointmentService._to_out(appointment)
