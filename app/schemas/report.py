from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ReportColumnMeta(BaseModel):
    key: str
    label: str
    type: Optional[str] = "string"  # string, number, date, boolean


class ReportEntityMeta(BaseModel):
    entity: str
    label: str
    description: str
    available_columns: List[ReportColumnMeta]


class ReportQueryRequest(BaseModel):
    entity: str = Field(..., description="Entidad a reportar: patients, recipes, appointments, payments, clinical_records, activity_logs")
    columns: Optional[List[str]] = Field(None, description="Columnas seleccionadas. Si está vacío, se incluyen las por defecto.")
    start_date: Optional[str] = Field(None, description="Fecha de inicio (YYYY-MM-DD)")
    end_date: Optional[str] = Field(None, description="Fecha de fin (YYYY-MM-DD)")
    status: Optional[str] = Field(None, description="Filtro opcional por estado")
    search: Optional[str] = Field(None, description="Término de búsqueda de texto")
    sort_by: Optional[str] = Field(None, description="Campo para ordenar")
    sort_order: Optional[str] = Field("desc", description="asc o desc")
    limit: Optional[int] = Field(500, ge=1, le=5000, description="Límite de registros")


class ReportQueryResponse(BaseModel):
    entity: str
    title: str
    generated_at: datetime
    columns: List[ReportColumnMeta]
    rows: List[Dict[str, Any]]
    total_rows: int
