from app.models.generated_report import GeneratedReport
from app.core.authorization import require_tenant
from app.core.exceptions import BadRequestException, NotFoundException, ForbiddenException
from app.services.report_service import ReportService
from app.services.backup_recovery_service import canonical
import json

class GeneratedReportService:
    @staticmethod
    def save(db, request, actor, report=None):
        from app.services.report_analytics_service import ReportAnalyticsService
        companies, _ = ReportAnalyticsService.scope(db, actor, request)
        company = companies[0].id if len(companies) == 1 else None
        if actor.role_id != 'SUPERADMIN' and not company: raise BadRequestException('Selecciona una empresa para guardar o exportar el reporte.')
        require_tenant(actor, company)
        report = report or ReportService.query_report_data(db, request, actor)
        row = GeneratedReport(tenant_id=company, created_by=actor.id, title=report.title, entity=request.entity, filters_json=request.model_dump_json(), snapshot_json=report.model_dump_json())
        db.add(row); db.commit(); db.refresh(row); return row

    @staticmethod
    def list(db, actor, company=None):
        query = db.query(GeneratedReport)
        if actor.role_id != 'SUPERADMIN':
            company = actor.tenant_id
            require_tenant(actor, company)
        if company: query = query.filter(GeneratedReport.tenant_id == company)
        if actor.role_id == 'NUTRICIONISTA': query = query.filter(GeneratedReport.created_by == actor.id)
        return query.order_by(GeneratedReport.created_at.desc()).limit(100).all()

    @staticmethod
    def get(db, actor, report_id):
        row = db.query(GeneratedReport).filter(GeneratedReport.id == report_id).first()
        if not row: raise NotFoundException('Reporte no encontrado.')
        require_tenant(actor, row.tenant_id)
        if actor.role_id == 'NUTRICIONISTA' and row.created_by != actor.id: raise ForbiddenException('El reporte pertenece a otro especialista.')
        return row
