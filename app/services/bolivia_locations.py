"""Local geographic catalog. Codes preserve the INE department/province hierarchy."""
import json
from pathlib import Path
from app.core.exceptions import BadRequestException

CATALOG = json.loads((Path(__file__).resolve().parents[1] / 'data' / 'bolivia_locations.json').read_text(encoding='utf-8'))
DEPARTMENTS = {d['code']: d for d in CATALOG}


def validate_department(code):
    if code not in DEPARTMENTS:
        raise BadRequestException('Selecciona un departamento válido de Bolivia.')
    return DEPARTMENTS[code]


def validate_location(department_code, province_code, municipality_code):
    department = validate_department(department_code)
    province = next((p for p in department['provinces'] if p['code'] == province_code), None)
    if not province:
        raise BadRequestException('Selecciona una provincia del departamento de la empresa.')
    if not any(m['code'] == municipality_code for m in province['municipalities']):
        raise BadRequestException('Selecciona un municipio de la provincia elegida.')
