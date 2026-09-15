from datetime import datetime, timezone
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.appointment import Appointment
from app.models.user import User
from app.models.tenant import Tenant
from app.schemas.appointment import AppointmentCreate, AppointmentOut, NutritionistOut
from app.services.notification_service import NotificationService


class AppointmentService:
    @staticmethod
    def create_appointment(db: Session, current_user: User, data: AppointmentCreate) -> AppointmentOut:
        # Validar nutricionista
        nutritionist = db.query(User).filter(User.id == data.nutritionist_id).first()
        if not nutritionist:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Nutricionista no encontrado",
            )

        tenant_id = data.tenant_id or current_user.tenant_id or nutritionist.tenant_id

        # Asegurar zona horaria UTC si es naive
        scheduled_at = data.scheduled_at
        if scheduled_at.tzinfo is None:
            scheduled_at = scheduled_at.replace(tzinfo=timezone.utc)

        appointment = Appointment(
            tenant_id=tenant_id,
            patient_id=current_user.id,
            nutritionist_id=data.nutritionist_id,
            scheduled_at=scheduled_at,
            reason=data.reason,
            status="PENDING",
        )
        db.add(appointment)
        db.commit()
        db.refresh(appointment)

        # 1. Notificar al nutricionista
        formatted_date = appointment.scheduled_at.strftime("%d/%m/%Y a las %H:%M")
        NotificationService.create_notification(
            db=db,
            user_id=nutritionist.id,
            title="Nueva Cita Pendiente",
            message=f"{current_user.full_name} agendó una cita para el {formatted_date}. Motivo: {appointment.reason or 'Consulta general'}.",
            type="CITA_CREADA",
            reference_id=appointment.id,
            tenant_id=tenant_id,
        )

        # 2. Notificar a los administradores de la organización
        if tenant_id:
            org_admins = (
                db.query(User)
                .filter(
                    User.tenant_id == tenant_id,
                    User.role_id.in_(["ADMIN_ORGANIZATION", "ADMIN_SAAS"]),
                    User.id != current_user.id,
                    User.id != nutritionist.id,
                )
                .all()
            )
            for admin in org_admins:
                NotificationService.create_notification(
                    db=db,
                    user_id=admin.id,
                    title="Nueva Cita Agendada",
                    message=f"Nueva solicitud de cita: {current_user.full_name} con {nutritionist.full_name} para el {formatted_date}.",
                    type="CITA_CREADA",
                    reference_id=appointment.id,
                    tenant_id=tenant_id,
                )

        return AppointmentService._to_out(appointment)

    @staticmethod
    def list_appointments(
        db: Session,
        current_user: User,
        status_filter: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[AppointmentOut]:
        query = db.query(Appointment)

        if current_user.role_id == "CLIENTE":
            query = query.filter(Appointment.patient_id == current_user.id)
        elif current_user.role_id == "NUTRICIONISTA":
            query = query.filter(Appointment.nutritionist_id == current_user.id)
        elif current_user.role_id == "ADMIN_ORGANIZATION":
            if current_user.tenant_id:
                query = query.filter(Appointment.tenant_id == current_user.tenant_id)
        elif current_user.role_id == "ADMIN_SAAS":
            if tenant_id:
                query = query.filter(Appointment.tenant_id == tenant_id)

        if status_filter and status_filter.upper() != "ALL":
            query = query.filter(Appointment.status == status_filter.upper())

        appointments = query.order_by(Appointment.scheduled_at.desc()).all()
        return [AppointmentService._to_out(a) for a in appointments]

    @staticmethod
    def confirm_appointment(db: Session, appointment_id: str, current_user: User) -> AppointmentOut:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cita no encontrada",
            )

        # Validar permisos
        if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para confirmar esta cita",
            )

        appointment.status = "CONFIRMED"
        appointment.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(appointment)

        # Notificar al paciente
        formatted_date = appointment.scheduled_at.strftime("%d/%m/%Y a las %H:%M")
        nutri_name = appointment.nutritionist.full_name if appointment.nutritionist else "tu especialista"
        NotificationService.create_notification(
            db=db,
            user_id=appointment.patient_id,
            title="¡Cita Confirmada!",
            message=f"Tu cita programada para el {formatted_date} con {nutri_name} ha sido confirmada.",
            type="CITA_CONFIRMADA",
            reference_id=appointment.id,
            tenant_id=appointment.tenant_id,
        )

        return AppointmentService._to_out(appointment)

    @staticmethod
    def cancel_appointment(
        db: Session,
        appointment_id: str,
        reason: Optional[str],
        current_user: User,
    ) -> AppointmentOut:
        appointment = db.query(Appointment).filter(Appointment.id == appointment_id).first()
        if not appointment:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cita no encontrada",
            )

        appointment.status = "CANCELLED"
        appointment.cancellation_reason = reason or "Cancelada por el administrador/especialista"
        appointment.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(appointment)

        formatted_date = appointment.scheduled_at.strftime("%d/%m/%Y a las %H:%M")

        # Si canceló el admin o nutri -> notificar al paciente
        if current_user.id != appointment.patient_id:
            NotificationService.create_notification(
                db=db,
                user_id=appointment.patient_id,
                title="Cita Cancelada",
                message=f"Tu cita para el {formatted_date} ha sido cancelada. Motivo: {appointment.cancellation_reason}.",
                type="CITA_CANCELADA",
                reference_id=appointment.id,
                tenant_id=appointment.tenant_id,
            )
        else:
            # Si canceló el paciente -> notificar al nutri
            NotificationService.create_notification(
                db=db,
                user_id=appointment.nutritionist_id,
                title="Cita Cancelada por Paciente",
                message=f"El paciente {current_user.full_name} canceló la cita del {formatted_date}. Motivo: {appointment.cancellation_reason}.",
                type="CITA_CANCELADA",
                reference_id=appointment.id,
                tenant_id=appointment.tenant_id,
            )

        return AppointmentService._to_out(appointment)

    @staticmethod
    def get_available_nutritionists(
        db: Session,
        current_user: User,
        tenant_id: Optional[str] = None,
    ) -> List[NutritionistOut]:
        target_tenant = tenant_id or current_user.tenant_id
        query = db.query(User).filter(User.role_id == "NUTRICIONISTA", User.is_active == True)
        if target_tenant:
            query = query.filter(User.tenant_id == target_tenant)

        nutritionists = query.all()
        # Si no hay en ese tenant específico, devolver todos los nutricionistas activos
        if not nutritionists:
            nutritionists = db.query(User).filter(User.role_id == "NUTRICIONISTA", User.is_active == True).all()

        return [
            NutritionistOut(
                id=n.id,
                full_name=n.full_name,
                email=n.email,
                phone=n.phone,
            )
            for n in nutritionists
        ]

    @staticmethod
    def _to_out(a: Appointment) -> AppointmentOut:
        return AppointmentOut(
            id=a.id,
            tenant_id=a.tenant_id,
            tenant_name=a.tenant.name if a.tenant else None,
            patient_id=a.patient_id,
            patient_name=a.patient.full_name if a.patient else None,
            patient_email=a.patient.email if a.patient else None,
            nutritionist_id=a.nutritionist_id,
            nutritionist_name=a.nutritionist.full_name if a.nutritionist else None,
            scheduled_at=a.scheduled_at,
            reason=a.reason,
            status=a.status,
            cancellation_reason=a.cancellation_reason,
            created_at=a.created_at,
            updated_at=a.updated_at,
        )
