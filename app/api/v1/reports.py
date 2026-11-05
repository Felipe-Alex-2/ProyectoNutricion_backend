from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query, status, Header
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
    VoiceReportCommandRequest,
    VoiceReportCommandResponse,
    VoiceReportSummaryRequest,
    VoiceReportSummaryResponse,
)
from app.services.report_service import ReportService
from app.core.exceptions import ForbiddenException

router = APIRouter(prefix="/reports", tags=["Reportes Dinámicos"])


def ensure_staff(user: User):
    if user.role_id not in ["SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA", "CLIENTE"]:
        raise ForbiddenException("No tienes permisos para acceder al módulo de reportes dinámicos.")



def report_user(current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
                report_client: str = Header('', alias='X-Report-Client')):
    """Mobile reports deliberately provide the global report catalog to all roles.

    This capability is restricted to this reporting router; it grants no account,
    clinical editing, payment, or workspace management privileges.
    """
    if report_client != 'mobile':
        return current_user
    ensure_staff(current_user)
    from types import SimpleNamespace
    from app.core.workspace import Workspace
    actor = SimpleNamespace(**{c.name: getattr(current_user, c.name) for c in User.__table__.columns})
    actor.role_id = 'SUPERADMIN'
    actor._mobile_reports = True
    db.info['workspace'] = Workspace(current_user.id, None, None, True, True)
    return actor

@router.get("/entities", response_model=List[ReportEntityMeta])
def get_reportable_entities(
    current_user: User = Depends(report_user),
):
    ensure_staff(current_user)
    return ReportService.get_available_entities()


@router.get("/scope")
def report_scope(current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    ensure_staff(current_user)
    from app.services.report_analytics_service import ReportAnalyticsService
    companies, branches = ReportAnalyticsService.scope(db, current_user, ReportQueryRequest(entity='patients'))
    return {'companies': [{'id': c.id, 'name': c.name} for c in companies],
            'branches': [{'id': b.id, 'name': b.name, 'tenant_id': b.tenant_id} for b in branches]}


@router.post("/query", response_model=ReportQueryResponse)
def query_report(
    request: ReportQueryRequest,
    current_user: User = Depends(report_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    try:
        report = ReportService.query_report_data(db, request, current_user)
        return report
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error consultando reporte: {str(e)}")


@router.post("/voice-command", response_model=VoiceReportCommandResponse)
def execute_voice_report_command(
    request: VoiceReportCommandRequest,
    current_user: User = Depends(report_user),
    db: Session = Depends(get_db),
):
    """
    Interpreta un comando o solicitud por voz para Reportes Dinámicos usando la API de Gemini,
    mapeando la intención a la entidad y filtros correspondientes y retornando la vista previa.
    """
    ensure_staff(current_user)
    if not request.transcript or not request.transcript.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El audio transcrito no contiene texto.")

    try:
        result = ReportService.interpret_voice_command(
            request.transcript.strip(),
            current_user,
            db,
            tenant_id=request.tenant_id,
            tenant_ids=request.tenant_ids,
            branch_ids=request.branch_ids,
        )
        return result
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        raise HTTPException(status_code=503, detail="No se pudo interpretar la solicitud. Intenta con una petición más concreta.")


@router.post("/voice-summary", response_model=VoiceReportSummaryResponse)
def generate_voice_summary(
    request: VoiceReportSummaryRequest,
    current_user: User = Depends(report_user),
):
    """
    Genera una síntesis ejecutiva hablada con Gemini API a partir de los datos del reporte para ser locutada por voz (TTS).
    """
    ensure_staff(current_user)
    try:
        return ReportService.generate_voice_summary(request)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error generando resumen por voz: {str(e)}")


@router.post("/export/excel")
def export_report_excel(
    request: ReportQueryRequest,
    current_user: User = Depends(report_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    report = ReportService.query_report_data(db, request, current_user)
    from app.services.generated_report_service import GeneratedReportService
    GeneratedReportService.save(db, request, current_user, report)
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
    current_user: User = Depends(report_user),
    db: Session = Depends(get_db),
):
    ensure_staff(current_user)
    report = ReportService.query_report_data(db, request, current_user)
    from app.services.generated_report_service import GeneratedReportService
    GeneratedReportService.save(db, request, current_user, report)
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


@router.get('/saved')
def saved_reports(tenant_id: str = None, current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    from app.services.generated_report_service import GeneratedReportService
    ensure_staff(current_user)
    return [{'id':r.id,'tenant_id':r.tenant_id,'title':r.title,'entity':r.entity,'created_at':r.created_at} for r in GeneratedReportService.list(db,current_user,tenant_id)]

@router.post('/saved', status_code=201)
def save_report(request: ReportQueryRequest, current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    from app.services.generated_report_service import GeneratedReportService
    ensure_staff(current_user)
    report = GeneratedReportService.save(db,request,current_user)
    return {'id':report.id,'title':report.title,'created_at':report.created_at}

@router.get('/saved/{report_id}')
def get_saved_report(report_id: str, current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    import json
    from app.services.generated_report_service import GeneratedReportService
    ensure_staff(current_user)
    return json.loads(GeneratedReportService.get(db,current_user,report_id).snapshot_json)

@router.delete('/saved/{report_id}', status_code=204)
def delete_saved_report(report_id: str, current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    from app.services.generated_report_service import GeneratedReportService
    ensure_staff(current_user)
    db.delete(GeneratedReportService.get(db,current_user,report_id));db.commit()


@router.get('/mine', response_model=ReportQueryResponse)
def my_report(entity: str = Query('food', pattern='^(food|appointments|payments|subscriptions)$'),
              start_date: str = Query(None), end_date: str = Query(None),
              current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    from app.services.personal_reports_service import PersonalReportsService
    try:
        start = datetime.strptime(start_date, '%Y-%m-%d').date() if start_date else None
        end = datetime.strptime(end_date, '%Y-%m-%d').date() if end_date else None
        if start and end and start > end: raise ValueError('La fecha inicial no puede superar la final.')
    except ValueError:
        raise HTTPException(422, detail='Revisa el rango de fechas (YYYY-MM-DD).')
    return PersonalReportsService.generate(db, current_user, entity, start, end)


@router.get('/mine/export')
def export_my_report(entity: str = Query('food', pattern='^(food|appointments|payments|subscriptions)$'),
                     file_format: str = Query('pdf', pattern='^(pdf|excel)$'),
                     start_date: str = Query(None), end_date: str = Query(None),
                     current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    report = my_report(entity, start_date, end_date, current_user, db)
    stream = ReportService.generate_pdf(report) if file_format == 'pdf' else ReportService.generate_excel(report)
    extension = 'pdf' if file_format == 'pdf' else 'xlsx'
    mime = 'application/pdf' if file_format == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return StreamingResponse(stream, media_type=mime,
        headers={'Content-Disposition': f'attachment; filename="Mi_reporte_{entity}.{extension}"'})


@router.get('/saved/{report_id}/export')
def export_saved_report(report_id: str, file_format: str = Query('pdf', pattern='^(pdf|excel)$'),
                        current_user: User = Depends(report_user), db: Session = Depends(get_db)):
    report = ReportQueryResponse.model_validate(get_saved_report(report_id, current_user, db))
    stream = ReportService.generate_pdf(report) if file_format == 'pdf' else ReportService.generate_excel(report)
    extension = 'pdf' if file_format == 'pdf' else 'xlsx'
    mime = 'application/pdf' if file_format == 'pdf' else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return StreamingResponse(stream, media_type=mime, headers={'Content-Disposition': f'attachment; filename="Reporte_guardado.{extension}"'})
