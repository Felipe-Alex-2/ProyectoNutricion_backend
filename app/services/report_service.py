import io
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc, asc

from app.models.user import User
from app.models.recipe import Recipe
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.clinical import ClinicalRecord
from app.models.activity_log import ActivityLog
from app.models.patient_link import PatientNutritionistLink
from app.schemas.report import (
    ReportColumnMeta,
    ReportEntityMeta,
    ReportQueryRequest,
    ReportQueryResponse,
)


class ReportService:

    ENTITIES_CONFIG: Dict[str, Dict[str, Any]] = {
        "patients": {
            "label": "Clientes / Pacientes",
            "description": "Directorio y estado de vinculación de clientes",
            "model": User,
            "columns": [
                {"key": "full_name", "label": "Nombre Completo", "type": "string"},
                {"key": "email", "label": "Correo Electrónico", "type": "string"},
                {"key": "phone", "label": "Teléfono", "type": "string"},
                {"key": "is_active", "label": "Activo", "type": "boolean"},
                {"key": "linked_status", "label": "Estado Vinculación", "type": "string"},
                {"key": "nutritionist_name", "label": "Especialista Asignado", "type": "string"},
                {"key": "created_at", "label": "Fecha Registro", "type": "date"},
            ],
            "default_columns": ["full_name", "email", "phone", "is_active", "linked_status", "created_at"],
        },
        "recipes": {
            "label": "Catálogo de Recetas",
            "description": "Recetas nutricionales con desglose de macronutrientes",
            "model": Recipe,
            "columns": [
                {"key": "title", "label": "Nombre de Receta", "type": "string"},
                {"key": "category", "label": "Categoría", "type": "string"},
                {"key": "calories", "label": "Calorías (kcal)", "type": "number"},
                {"key": "protein", "label": "Proteína (g)", "type": "number"},
                {"key": "carbohydrates", "label": "Carbohidratos (g)", "type": "number"},
                {"key": "fats", "label": "Grasas (g)", "type": "number"},
                {"key": "fiber", "label": "Fibra (g)", "type": "number"},
                {"key": "difficulty", "label": "Dificultad", "type": "string"},
                {"key": "servings", "label": "Porciones", "type": "number"},
                {"key": "created_at", "label": "Fecha Creación", "type": "date"},
            ],
            "default_columns": ["title", "category", "calories", "protein", "carbohydrates", "fats", "difficulty"],
        },
        "appointments": {
            "label": "Gestión de Citas",
            "description": "Historial y agenda de consultas nutricionales",
            "model": Appointment,
            "columns": [
                {"key": "patient_name", "label": "Paciente", "type": "string"},
                {"key": "nutritionist_name", "label": "Especialista", "type": "string"},
                {"key": "scheduled_at", "label": "Fecha y Hora Cita", "type": "date"},
                {"key": "status", "label": "Estado", "type": "string"},
                {"key": "reason", "label": "Motivo", "type": "string"},
                {"key": "created_at", "label": "Fecha Solicitud", "type": "date"},
            ],
            "default_columns": ["patient_name", "nutritionist_name", "scheduled_at", "status", "reason"],
        },
        "payments": {
            "label": "Caja y Cobros (Pagos)",
            "description": "Transacciones de suscripciones y servicios PayPal",
            "model": Payment,
            "columns": [
                {"key": "user_name", "label": "Cliente", "type": "string"},
                {"key": "amount", "label": "Monto", "type": "number"},
                {"key": "currency", "label": "Moneda", "type": "string"},
                {"key": "status", "label": "Estado", "type": "string"},
                {"key": "payment_method", "label": "Método", "type": "string"},
                {"key": "paypal_order_id", "label": "Ref. PayPal", "type": "string"},
                {"key": "created_at", "label": "Fecha Transacción", "type": "date"},
            ],
            "default_columns": ["user_name", "amount", "currency", "status", "payment_method", "created_at"],
        },
        "clinical_records": {
            "label": "Fichas Clínicas y Diagnósticos",
            "description": "Evolución clínica, metas y diagnósticos nutricionales",
            "model": ClinicalRecord,
            "columns": [
                {"key": "patient_name", "label": "Paciente", "type": "string"},
                {"key": "nutritionist_name", "label": "Especialista", "type": "string"},
                {"key": "diagnosis", "label": "Diagnóstico Clínico", "type": "string"},
                {"key": "clinical_goals", "label": "Metas Terapéuticas", "type": "string"},
                {"key": "created_at", "label": "Fecha Asiento", "type": "date"},
            ],
            "default_columns": ["patient_name", "nutritionist_name", "diagnosis", "clinical_goals", "created_at"],
        },
        "activity_logs": {
            "label": "Bitácora de Auditoría",
            "description": "Registro de eventos de seguridad y transacciones del sistema",
            "model": ActivityLog,
            "columns": [
                {"key": "user_name", "label": "Usuario", "type": "string"},
                {"key": "user_email", "label": "Correo", "type": "string"},
                {"key": "action", "label": "Acción", "type": "string"},
                {"key": "category", "label": "Categoría", "type": "string"},
                {"key": "description", "label": "Detalles", "type": "string"},
                {"key": "ip_address", "label": "Dirección IP", "type": "string"},
                {"key": "created_at", "label": "Fecha / Hora", "type": "date"},
            ],
            "default_columns": ["user_name", "action", "category", "description", "ip_address", "created_at"],
        },
    }

    @classmethod
    def get_available_entities(cls) -> List[ReportEntityMeta]:
        result = []
        for key, conf in cls.ENTITIES_CONFIG.items():
            cols = [ReportColumnMeta(**c) for c in conf["columns"]]
            result.append(
                ReportEntityMeta(
                    entity=key,
                    label=conf["label"],
                    description=conf["description"],
                    available_columns=cols,
                )
            )
        return result

    @classmethod
    def query_report_data(
        cls,
        db: Session,
        req: ReportQueryRequest,
        current_user: User,
    ) -> ReportQueryResponse:
        entity_key = req.entity.lower().strip()
        if entity_key not in cls.ENTITIES_CONFIG:
            raise ValueError(f"Entidad no válida: {entity_key}")

        conf = cls.ENTITIES_CONFIG[entity_key]
        all_cols_dict = {c["key"]: c for c in conf["columns"]}

        # Resolver columnas seleccionadas
        if req.columns and len(req.columns) > 0:
            selected_keys = [k for k in req.columns if k in all_cols_dict]
        else:
            selected_keys = conf["default_columns"]

        selected_cols_meta = [ReportColumnMeta(**all_cols_dict[k]) for k in selected_keys]

        # Extraer registros según entidad
        rows: List[Dict[str, Any]] = []

        if entity_key == "patients":
            q = db.query(User).filter(User.role_id == "CLIENTE")
            if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
                q = q.filter(User.tenant_id == current_user.tenant_id)
            if req.status:
                if req.status.lower() == "activo":
                    q = q.filter(User.is_active == True)
                elif req.status.lower() == "inactivo":
                    q = q.filter(User.is_active == False)
            if req.search:
                s = f"%{req.search.lower()}%"
                q = q.filter(or_(User.full_name.ilike(s), User.email.ilike(s), User.phone.ilike(s)))
            if req.start_date:
                q = q.filter(User.created_at >= req.start_date)
            if req.end_date:
                q = q.filter(User.created_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(User.created_at.desc()).limit(req.limit).all()
            for u in items:
                link = db.query(PatientNutritionistLink).filter(PatientNutritionistLink.patient_id == u.id).first()
                nutri_name = "Sin asignar"
                if link and link.nutritionist_id:
                    nutri = db.query(User).filter(User.id == link.nutritionist_id).first()
                    if nutri:
                        nutri_name = nutri.full_name

                rows.append({
                    "full_name": u.full_name,
                    "email": u.email,
                    "phone": u.phone or "N/A",
                    "is_active": "Sí" if u.is_active else "No",
                    "linked_status": link.status if link else "UNLINKED",
                    "nutritionist_name": nutri_name,
                    "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
                })

        elif entity_key == "recipes":
            q = db.query(Recipe).filter(Recipe.is_active == True)
            if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
                q = q.filter((Recipe.tenant_id == current_user.tenant_id) | (Recipe.tenant_id == None))
            if req.search:
                s = f"%{req.search.lower()}%"
                q = q.filter(or_(Recipe.title.ilike(s), Recipe.category.ilike(s)))
            if req.status:
                q = q.filter(Recipe.category == req.status)
            if req.start_date:
                q = q.filter(Recipe.created_at >= req.start_date)
            if req.end_date:
                q = q.filter(Recipe.created_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(Recipe.created_at.desc()).limit(req.limit).all()
            for r in items:
                rows.append({
                    "title": r.title,
                    "category": r.category,
                    "calories": r.calories,
                    "protein": r.protein,
                    "carbohydrates": r.carbohydrates,
                    "fats": r.fats,
                    "fiber": r.fiber,
                    "difficulty": r.difficulty,
                    "servings": r.servings,
                    "created_at": r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                })

        elif entity_key == "appointments":
            q = db.query(Appointment)
            if current_user.role_id == "NUTRICIONISTA":
                q = q.filter(Appointment.nutritionist_id == current_user.id)
            elif current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
                q = q.filter(Appointment.tenant_id == current_user.tenant_id)
            if req.status:
                q = q.filter(Appointment.status == req.status.upper())
            if req.start_date:
                q = q.filter(Appointment.scheduled_at >= req.start_date)
            if req.end_date:
                q = q.filter(Appointment.scheduled_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(Appointment.scheduled_at.desc()).limit(req.limit).all()
            for a in items:
                p = db.query(User).filter(User.id == a.patient_id).first()
                n = db.query(User).filter(User.id == a.nutritionist_id).first()
                rows.append({
                    "patient_name": p.full_name if p else "N/A",
                    "nutritionist_name": n.full_name if n else "N/A",
                    "scheduled_at": a.scheduled_at.strftime("%Y-%m-%d %H:%M") if a.scheduled_at else "",
                    "status": a.status,
                    "reason": a.reason or "Consulta",
                    "created_at": a.created_at.strftime("%Y-%m-%d %H:%M") if a.created_at else "",
                })

        elif entity_key == "payments":
            q = db.query(Payment)
            if current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
                q = q.filter(Payment.tenant_id == current_user.tenant_id)
            if req.status:
                q = q.filter(Payment.status == req.status.upper())
            if req.start_date:
                q = q.filter(Payment.created_at >= req.start_date)
            if req.end_date:
                q = q.filter(Payment.created_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(Payment.created_at.desc()).limit(req.limit).all()
            for p in items:
                u = db.query(User).filter(User.id == p.user_id).first()
                rows.append({
                    "user_name": u.full_name if u else "N/A",
                    "amount": f"{p.amount:.2f}",
                    "currency": p.currency,
                    "status": p.status,
                    "payment_method": p.payment_method,
                    "paypal_order_id": p.paypal_order_id or "N/A",
                    "created_at": p.created_at.strftime("%Y-%m-%d %H:%M") if p.created_at else "",
                })

        elif entity_key == "clinical_records":
            q = db.query(ClinicalRecord)
            if current_user.role_id == "NUTRICIONISTA":
                q = q.filter(ClinicalRecord.nutritionist_id == current_user.id)
            elif current_user.role_id != "ADMIN_SAAS" and current_user.tenant_id:
                q = q.filter(ClinicalRecord.tenant_id == current_user.tenant_id)
            if req.start_date:
                q = q.filter(ClinicalRecord.created_at >= req.start_date)
            if req.end_date:
                q = q.filter(ClinicalRecord.created_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(ClinicalRecord.created_at.desc()).limit(req.limit).all()
            for c in items:
                p = db.query(User).filter(User.id == c.patient_id).first()
                n = db.query(User).filter(User.id == c.nutritionist_id).first()
                rows.append({
                    "patient_name": p.full_name if p else "N/A",
                    "nutritionist_name": n.full_name if n else "N/A",
                    "diagnosis": c.diagnosis,
                    "clinical_goals": c.clinical_goals or "N/A",
                    "created_at": c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
                })

        elif entity_key == "activity_logs":
            q = db.query(ActivityLog)
            if req.status:
                q = q.filter(ActivityLog.category == req.status.upper())
            if req.search:
                s = f"%{req.search.lower()}%"
                q = q.filter(or_(ActivityLog.action.ilike(s), ActivityLog.user_name.ilike(s), ActivityLog.description.ilike(s)))
            if req.start_date:
                q = q.filter(ActivityLog.created_at >= req.start_date)
            if req.end_date:
                q = q.filter(ActivityLog.created_at <= f"{req.end_date} 23:59:59")

            items = q.order_by(ActivityLog.created_at.desc()).limit(req.limit).all()
            for l in items:
                rows.append({
                    "user_name": l.user_name or "Sistema",
                    "user_email": l.user_email or "N/A",
                    "action": l.action,
                    "category": l.category or "INFO",
                    "description": l.description or "",
                    "ip_address": l.ip_address or "Local",
                    "created_at": l.created_at.strftime("%Y-%m-%d %H:%M") if l.created_at else "",
                })

        return ReportQueryResponse(
            entity=entity_key,
            title=conf["label"],
            generated_at=datetime.now(timezone.utc),
            columns=selected_cols_meta,
            rows=rows,
            total_rows=len(rows),
        )

    @classmethod
    def generate_excel(cls, report: ReportQueryResponse) -> io.BytesIO:
        """Exporta el reporte a un libro de trabajo Excel (.xlsx) con estilo profesional."""
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        import re
        clean_sheet_title = re.sub(r'[\\/*?:\[\]]', ' ', report.title).strip()[:31]
        ws.title = clean_sheet_title or "Reporte"

        # Colores institucionales NutriSalud (#206443)
        header_fill = PatternFill(start_color="206443", end_color="206443", fill_type="solid")
        header_font = Font(name="Segoe UI", size=11, bold=True, color="FFFFFF")
        title_font = Font(name="Segoe UI", size=14, bold=True, color="1B4D3E")
        meta_font = Font(name="Segoe UI", size=9, italic=True, color="666666")
        data_font = Font(name="Segoe UI", size=10, color="222222")
        zebra_fill = PatternFill(start_color="F7FAF8", end_color="F7FAF8", fill_type="solid")
        thin_border = Border(
            left=Side(style='thin', color='E0E0E0'),
            right=Side(style='thin', color='E0E0E0'),
            top=Side(style='thin', color='E0E0E0'),
            bottom=Side(style='thin', color='E0E0E0')
        )

        # 1. Título y metadatos
        ws.merge_cells("A1:F1")
        title_cell = ws["A1"]
        title_cell.value = f"NutriSalud - Reporte Dinámico: {report.title}"
        title_cell.font = title_font

        ws["A2"].value = f"Generado: {report.generated_at.strftime('%Y-%m-%d %H:%M:%S UTC')} | Total registros: {report.total_rows}"
        ws["A2"].font = meta_font

        # 2. Encabezados de columnas
        start_row = 4
        for col_idx, col in enumerate(report.columns, start=1):
            cell = ws.cell(row=start_row, column=col_idx, value=col.label)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal="center", vertical="center")
            cell.border = thin_border
        ws.row_dimensions[start_row].height = 24

        # 3. Filas de datos
        for row_idx, row_data in enumerate(report.rows, start=start_row + 1):
            is_zebra = (row_idx % 2 == 0)
            for col_idx, col in enumerate(report.columns, start=1):
                val = row_data.get(col.key, "")
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.font = data_font
                cell.border = thin_border
                if is_zebra:
                    cell.fill = zebra_fill
                if col.type == "number":
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
            ws.row_dimensions[row_idx].height = 20

        # Autoajustar ancho de columnas
        for col_idx, col in enumerate(report.columns, start=1):
            col_letter = get_column_letter(col_idx)
            max_len = len(col.label)
            for r in report.rows:
                val_str = str(r.get(col.key, ""))
                if len(val_str) > max_len:
                    max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(12, min(max_len + 4, 45))

        stream = io.BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    @classmethod
    def generate_pdf(cls, report: ReportQueryResponse) -> io.BytesIO:
        """Exporta el reporte a un documento PDF con tabla formateada e identidad visual."""
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

        stream = io.BytesIO()
        # Usar orientación horizontal (landscape) para tablas dinámicas
        doc = SimpleDocTemplate(
            stream,
            pagesize=landscape(letter),
            rightMargin=30,
            leftMargin=30,
            topMargin=30,
            bottomMargin=30,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            textColor=colors.HexColor("#206443"),
            spaceAfter=4,
        )
        meta_style = ParagraphStyle(
            name="ReportMeta",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            textColor=colors.HexColor("#555555"),
            spaceAfter=12,
        )
        table_header_style = ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=colors.white,
            alignment=1,  # Center
        )
        table_cell_style = ParagraphStyle(
            name="TableCell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            textColor=colors.HexColor("#222222"),
        )

        elements = []

        # Encabezado
        elements.append(Paragraph(f"NutriSalud - Reporte Oficial: {report.title}", title_style))
        elements.append(
            Paragraph(
                f"Emitido: {report.generated_at.strftime('%Y-%m-%d %H:%M UTC')} | "
                f"Total de registros: {report.total_rows} | Sistema Multi-Tenant NutriSalud",
                meta_style,
            )
        )
        elements.append(Spacer(1, 8))

        # Construir matriz de datos para la tabla
        header_row = [Paragraph(c.label, table_header_style) for c in report.columns]
        table_data = [header_row]

        for row in report.rows:
            row_cells = []
            for col in report.columns:
                val = str(row.get(col.key, ""))
                # Truncar textos demasiado largos en PDF para evitar saltos masivos
                if len(val) > 70:
                    val = val[:67] + "..."
                row_cells.append(Paragraph(val, table_cell_style))
            table_data.append(row_cells)

        # Crear tabla y aplicar estilos
        t = Table(table_data, repeatRows=1)
        t.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#206443")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
                ("TOPPADDING", (0, 0), (-1, 0), 6),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7FAF8")]),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E0E0E0")),
                ("TOPPADDING", (0, 1), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 1), (-1, -1), 4),
            ])
        )

        elements.append(t)
        doc.build(elements)

        stream.seek(0)
        return stream
