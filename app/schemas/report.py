from datetime import datetime
from typing import Any, Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class ReportColumnMeta(BaseModel):
    key: str
    label: str
    type: Optional[str] = "string"  # string, number, date, boolean


class ReportEntityMeta(BaseModel):
    entity: str
    label: str
    description: str
    available_columns: List[ReportColumnMeta]


class ReportFilter(BaseModel):
    field: str = Field(..., max_length=50)
    operator: Literal['eq','ne','gt','gte','lt','lte','contains','in'] = 'eq'
    value: str | int | float | bool | None | List[str | int | float | bool | None]


class ReportQueryRequest(BaseModel):
    filters: List[ReportFilter] = Field(default_factory=list, max_length=20)
    tenant_ids: List[str] = Field(default_factory=list, max_length=100)
    branch_ids: List[str] = Field(default_factory=list, max_length=100)
    aggregate: bool = False
    group_by: Optional[Literal['company', 'branch', 'month', 'status', 'nutritionist', 'payment_method']] = None
    metric: Literal['count', 'sum', 'average', 'unique_patients', 'cancellation_rate'] = 'count'
    value_field: Optional[str] = None
    currency: Optional[str] = Field(None, pattern=r'^[A-Z]{3}$')

    @field_validator('start_date', 'end_date', check_fields=False)
    @classmethod
    def valid_date(cls, value):
        if value: datetime.strptime(value, '%Y-%m-%d')
        return value

    @field_validator('status', check_fields=False)
    @classmethod
    def normalize_status(cls, value):
        return None if value and value.strip().upper() in ('ALL','TODOS','TODAS') else value.strip() if value else None

    @model_validator(mode='after')
    def valid_range(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError('La fecha inicial no puede superar la fecha final.')
        return self

    entity: str = Field(..., description="Entidad a reportar: patients, recipes, appointments, payments, clinical_records, activity_logs")
    columns: Optional[List[str]] = Field(None, description="Columnas seleccionadas. Si está vacío, se incluyen las por defecto.")
    start_date: Optional[str] = Field(None, description="Fecha de inicio (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Fecha de fin (YYYY-MM-DD)")
    status: Optional[str] = Field(None, description="Filtro opcional por estado")
    search: Optional[str] = Field(None, description="Término de búsqueda de texto")
    sort_by: Optional[str] = Field(None, description="Campo para ordenar")
    sort_order: Literal["asc", "desc"] = "desc"
    limit: Optional[int] = Field(500, ge=1, le=5000, description="Límite de registros")
    tenant_id: Optional[str] = Field(None, description="Filtro opcional por organización / tenant (SUPERADMIN)")


class ReportQueryResponse(BaseModel):
    entity: str
    title: str
    generated_at: datetime
    columns: List[ReportColumnMeta]
    rows: List[Dict[str, Any]]
    total_rows: int
    summary: Optional[str] = None
    notes: List[str] = Field(default_factory=list)
    chart: Optional[str] = None


class VoiceReportCommandRequest(BaseModel):
    transcript: str = Field(..., min_length=2, max_length=2000, description="Texto dictado o instrucción por voz del usuario")
    tenant_id: Optional[str] = Field(None, description="Filtro opcional por organización / tenant (SUPERADMIN)")
    tenant_ids: List[str] = Field(default_factory=list, max_length=100)
    branch_ids: List[str] = Field(default_factory=list, max_length=100)


class VoiceReportCommandResponse(BaseModel):
    parsed_request: ReportQueryRequest
    explanation: str
    report_data: Optional[ReportQueryResponse] = None


class VoiceReportSummaryRequest(BaseModel):
    summary: Optional[str] = Field(None, max_length=4000)
    notes: List[str] = Field(default_factory=list, max_length=30)
    entity: str
    title: str
    total_rows: int
    columns: List[str]
    sample_rows: List[Dict[str, Any]]


class VoiceReportSummaryResponse(BaseModel):
    summary_text: str
    bullet_points: List[str]
