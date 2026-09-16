from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.activity_log import ActivityLog
from app.schemas.report import (
    ReportEntityMeta,
    ReportQueryRequest,
    ReportQueryResponse,
)
from app.services.report_service import ReportService
from app.core.exceptions import ForbiddenException

router = APIRouter(prefix="/reports", tags=["Reportes Dinámicos"])


def ensure_staff(user: User):
    if user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise ForbiddenException("No tienes permisos para acceder al módulo de reportes dinámicos.")


@router.get("/entities", response_model=List[ReportEntityMeta])
def get_reportable_entities(
    current_user: User = Depends(get_current_user),
):
    ensure_staff(current_user)
    return ReportService.get_available_entities()


@router.post("/query", response_model=ReportQueryResponse)
def query_report(
    request: ReportQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    try:
        report = ReportService.query_report_data(db, request, current_user)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error consultando reporte: {str(e)}")


@router.post("/export/excel")
def export_report_excel(
    request: ReportQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    report = ReportService.query_report_data(db, request, current_user)
    excel_stream = ReportService.generate_excel(report)

    # Registrar en bitácora
    try:
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="REPORTE_EXCEL_EXPORTADO",
            description=f"Exportación de reporte dinámico '{report.title}' a Excel ({report.total_rows} filas).",
            category="REPORTS",
        ))
        db.commit()
    except Exception:
        pass

    filename = f"reporte_{request.entity}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        excel_stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/pdf")
def export_report_pdf(
    request: ReportQueryRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    report = ReportService.query_report_data(db, request, current_user)
    pdf_stream = ReportService.generate_pdf(report)

    # Registrar en bitácora
    try:
        db.add(ActivityLog(
            user_id=current_user.id,
            user_email=current_user.email,
            user_name=current_user.full_name,
            action="REPORTE_PDF_EXPORTADO",
            description=f"Exportación de reporte dinámico '{report.title}' a PDF ({report.total_rows} filas).",
            category="REPORTS",
        ))
        db.commit()
    except Exception:
        pass

    filename = f"reporte_{request.entity}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return StreamingResponse(
        pdf_stream,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
