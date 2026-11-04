"""Self-service reports: ownership always comes from the authenticated user."""
import json
from datetime import datetime, time, timedelta, timezone
from app.models.ai_nutrition import FoodRecord
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.subscription_receipt import SubscriptionReceipt
from app.schemas.report import ReportQueryResponse, ReportColumnMeta


class PersonalReportsService:
    @staticmethod
    def generate(db, user, entity, start_date=None, end_date=None):
        def stamp(value):
            return value.strftime('%Y-%m-%d %H:%M') if value else ''
        if entity == 'food':
            query = db.query(FoodRecord).filter_by(patient_id=user.id)
            date_column = FoodRecord.created_at
            title = 'Mi alimentación y fotos IA'
            columns = [('date','Registro'),('description','Comida'),('source','Origen'),
                       ('calories','kcal'),('protein','Proteínas (g)'),('carbs','Carbohidratos (g)'),('fats','Grasas (g)')]
            def row(item):
                try: details = json.loads(item.result_json)
                except (ValueError, TypeError): details = {}
                return dict(date=stamp(item.created_at), description=details.get('description') or item.notes or 'Análisis de alimento',
                    source='Manual' if item.confidence == 'manual' else 'Foto IA', calories=item.estimated_calories,
                    protein=item.estimated_protein, carbs=item.estimated_carbs, fats=item.estimated_fats)
        elif entity == 'appointments':
            query = db.query(Appointment).filter_by(patient_id=user.id)
            date_column = Appointment.scheduled_at
            title = 'Mis citas'
            columns = [('date','Fecha de cita'),('professional','Profesional'),('reason','Motivo'),('status','Estado')]
            def row(item):
                return dict(date=stamp(item.scheduled_at), professional=item.nutritionist.full_name if item.nutritionist else '',
                            reason=item.reason or 'Consulta general', status=item.status)
        elif entity == 'payments':
            query = db.query(Payment).filter_by(patient_id=user.id, cashier_id=None, status='COMPLETED')
            date_column = Payment.paid_at
            title = 'Mis pagos y recargas'
            columns = [('date','Fecha de pago'),('concept','Concepto'),('amount','Importe'),('currency','Moneda'),('method','Método')]
            def row(item):
                return dict(date=stamp(item.paid_at), concept=item.concept, amount=item.amount,
                            currency=item.currency, method=item.payment_method)
        else:
            query = db.query(SubscriptionReceipt).filter_by(user_id=user.id)
            date_column = SubscriptionReceipt.paid_at
            title = 'Mis pagos de suscripción'
            columns = [('date','Fecha de pago'),('concept','Concepto'),('amount','Importe'),('currency','Moneda'),('expires','Vigencia hasta')]
            def row(item):
                return dict(date=stamp(item.paid_at), concept=item.plan_name, amount=float(item.amount),
                            currency=item.currency, expires=stamp(item.expires_at))
        if start_date:
            query = query.filter(date_column >= datetime.combine(start_date, time.min))
        if end_date:
            query = query.filter(date_column < datetime.combine(end_date + timedelta(days=1), time.min))
        total = query.count()
        records = query.order_by(date_column.desc()).limit(500).all()
        notes = ['Solo incluye registros de tu cuenta.']
        if entity == 'food': notes.append('Los nutrientes registrados por IA son estimaciones. Las fechas corresponden al registro.')
        if entity == 'payments': notes.append('Las recargas añaden saldo a wallet; se muestran separadas por concepto del pago de consultas.')
        if total > 500: notes.append('Se muestran los 500 registros más recientes. Reduce el rango de fechas para ver los restantes.')
        return ReportQueryResponse(entity=entity, title=title, generated_at=datetime.now(timezone.utc),
            columns=[ReportColumnMeta(key=k,label=label,type='number' if k in {'calories','protein','carbs','fats','amount'} else 'string') for k,label in columns],
            rows=[row(item) for item in records], total_rows=total, summary=f'{total} registros encontrados.', notes=notes)
