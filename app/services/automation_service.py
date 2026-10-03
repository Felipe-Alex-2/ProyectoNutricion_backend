import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.appointment import Appointment
from app.models.clinical import PatientAnamnesis
from app.models.notification import Notification
from app.models.patient_link import PatientNutritionistLink
from app.models.ai_nutrition import AutomationConfig, DeviceToken
from app.services.expert_system_service import ExpertSystemService
from app.services.gemini_service import GeminiService

logger = logging.getLogger(__name__)


class AutomationService:
    """Motor RPA de automatizaciones clínicas, recordatorios y seguimiento médico."""

    @classmethod
    def check_appointment_reminders(cls, db: Session) -> Dict[str, Any]:
        """
        Recordatorio de cita (1h antes):
        Busca citas programadas entre now + 50 min y now + 70 min que no hayan enviado recordatorio.
        """
        now = datetime.now(timezone.utc)
        start_window = now + timedelta(minutes=50)
        end_window = now + timedelta(minutes=70)

        appointments = (
            db.query(Appointment)
            .filter(
                Appointment.status == "CONFIRMED",
                Appointment.reminder_sent == False,
                Appointment.scheduled_at >= start_window,
                Appointment.scheduled_at <= end_window,
            )
            .all()
        )

        sent_count = 0
        for appt in appointments:
            patient = db.query(User).filter(User.id == appt.patient_id).first()
            nutritionist = db.query(User).filter(User.id == appt.nutritionist_id).first()

            hora_str = appt.scheduled_at.strftime("%H:%M")
            # Notificación al paciente
            if patient:
                db.add(
                    Notification(
                        user_id=patient.id,
                        tenant_id=appt.tenant_id or patient.tenant_id,
                        title="Recordatorio: Cita nutricional en 1 hora",
                        message=f"Hola {patient.full_name}, tienes una consulta programada para hoy a las {hora_str} con {nutritionist.full_name if nutritionist else 'tu especialista'}.",
                        type="RECORDATORIO_CITA",
                        reference_id=appt.id,
                    )
                )

            # Notificación al nutricionista
            if nutritionist:
                db.add(
                    Notification(
                        user_id=nutritionist.id,
                        tenant_id=appt.tenant_id or nutritionist.tenant_id,
                        title="Cita próxima en 1 hora",
                        message=f"Tienes consulta agendada a las {hora_str} con el paciente {patient.full_name if patient else 'agendado'}.",
                        type="RECORDATORIO_CITA",
                        reference_id=appt.id,
                    )
                )

            appt.reminder_sent = True
            sent_count += 1

        db.commit()

        # Actualizar last_run_at de la automatización
        cfg = db.query(AutomationConfig).filter(AutomationConfig.key == "RECORDATORIO_CITAS").first()
        if cfg:
            cfg.last_run_at = now
            db.commit()

        return {
            "status": "success",
            "evaluated_window": f"{start_window.strftime('%H:%M')} - {end_window.strftime('%H:%M')}",
            "reminders_sent": sent_count,
        }

    @classmethod
    def run_weekly_habits_evaluation(cls, db: Session) -> Dict[str, Any]:
        """
        Aviso semanal de hábitos:
        Evalúa el cumplimiento de cada paciente con ficha clínica y genera notificaciones en su bandeja.
        """
        now = datetime.now(timezone.utc)
        anamneses = db.query(PatientAnamnesis).all()
        processed = 0

        for a in anamneses:
            patient = db.query(User).filter(User.id == a.patient_id).first()
            if not patient or not patient.is_active:
                continue

            result = ExpertSystemService.evaluate_weekly_habits(
                db=db,
                anamnesis=a,
                patient_name=patient.full_name,
            )

            # Guardar notificación en la bandeja existente
            notif = Notification(
                user_id=patient.id,
                tenant_id=patient.tenant_id,
                title="Evaluación Semanal de Hábitos Saludables",
                message=result.notification_message,
                type=result.evaluation_status,  # TODO_BIEN o HABITOS_POR_MEJORAR
                reference_id=a.id,
            )
            db.add(notif)
            processed += 1

        db.commit()

        cfg = db.query(AutomationConfig).filter(AutomationConfig.key == "AVISO_SEMANAL_HABITOS").first()
        if cfg:
            cfg.last_run_at = now
            db.commit()

        return {
            "status": "success",
            "patients_evaluated": processed,
            "executed_at": now.isoformat(),
        }

    @classmethod
    def generate_nutritionist_summary(cls, db: Session, nutritionist_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Seguimiento al médico/nutricionista:
        Calcula resumen del estado de los pacientes vinculados y genera una alerta consolidada en su bandeja.
        """
        now = datetime.now(timezone.utc)
        query = db.query(User).filter(User.role_id.in_(["NUTRICIONISTA", "ADMIN_ORGANIZATION"]))
        if nutritionist_id:
            query = query.filter(User.id == nutritionist_id)

        nutritionists = query.all()
        summaries_sent = 0

        for nutri in nutritionists:
            links = (
                db.query(PatientNutritionistLink)
                .filter(
                    PatientNutritionistLink.nutritionist_id == nutri.id,
                    PatientNutritionistLink.status == "LINKED",
                )
                .all()
            )

            patient_ids = [l.patient_id for l in links if l.patient_id]
            if not patient_ids:
                continue

            patients_with_issues = []
            patients_optimal = []

            for pid in patient_ids:
                p_user = db.query(User).filter(User.id == pid).first()
                p_anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == pid).first()
                if not p_user or not p_anamnesis:
                    continue

                eval_res = ExpertSystemService.evaluate_weekly_habits(db, p_anamnesis, p_user.full_name)
                if eval_res.unfulfilled_count >= 2:
                    failed_names = [it.habit.lower() for it in eval_res.items if not it.fulfilled]
                    patients_with_issues.append(f"{p_user.full_name} ({', '.join(failed_names)})")
                else:
                    patients_optimal.append(p_user.full_name)

            # Generar texto de resumen
            summary_text = (
                f"Resumen semanal de tu cohorte ({len(patient_ids)} pacientes vinculados): "
                f"{len(patients_optimal)} pacientes con óptima adherencia. "
            )
            if patients_with_issues:
                summary_text += f"{len(patients_with_issues)} requieren seguimiento en hábitos: {'; '.join(patients_with_issues[:4])}."
            else:
                summary_text += "¡Todos los pacientes registrados mantienen excelentes hábitos!"

            # Redacción con Gemini si está configurada (2-3 líneas estructuradas)
            if GeminiService.is_configured():
                ai_prompt = (
                    f"Redacta un breve resumen clínico formal y conciso de 2 líneas para el nutricionista {nutri.full_name} "
                    f"basado en estos datos: {summary_text}. No agregues datos no mencionados."
                )
                refined = GeminiService.generate_text(ai_prompt, temperature=0.2, max_output_tokens=150)
                if refined:
                    summary_text = refined.strip()

            db.add(
                Notification(
                    user_id=nutri.id,
                    tenant_id=nutri.tenant_id,
                    title="Resumen Semanal de Pacientes Asignados",
                    message=summary_text,
                    type="RESUMEN_SEGUIMIENTO_NUTRI",
                )
            )
            summaries_sent += 1

        db.commit()
        return {
            "status": "success",
            "summaries_generated": summaries_sent,
            "executed_at": now.isoformat(),
        }

    @classmethod
    def register_device_token(
        cls,
        db: Session,
        user_id: str,
        token: str,
        platform: str = "android",
    ) -> DeviceToken:
        """Registra o actualiza el token FCM del dispositivo para notificaciones push."""
        existing = db.query(DeviceToken).filter(DeviceToken.token == token).first()
        if existing:
            existing.user_id = user_id
            existing.platform = platform
            existing.updated_at = datetime.now(timezone.utc)
            dev_token = existing
        else:
            dev_token = DeviceToken(
                user_id=user_id,
                token=token,
                platform=platform,
            )
            db.add(dev_token)

        db.commit()
        db.refresh(dev_token)
        return dev_token
