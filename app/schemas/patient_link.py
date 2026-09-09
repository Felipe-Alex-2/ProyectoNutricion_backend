from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class GenerateLinkRequest(BaseModel):
    whatsapp_number: Optional[str] = "+591 73683564"
    tenant_id: Optional[str] = None
    notes: Optional[str] = None


class ClaimLinkRequest(BaseModel):
    pairing_code: str = Field(..., min_length=4, max_length=20, description="Código de vinculación de 6 caracteres")

    @field_validator("pairing_code")
    @classmethod
    def validate_pairing_code(cls, v: str) -> str:
        v = v.strip().upper()
        if len(v) < 4:
            raise ValueError("El código de vinculación no es válido")
        return v



class PatientLinkResponse(BaseModel):
    id: str
    tenant_id: Optional[str] = None
    tenant_name: Optional[str] = None
    nutritionist_id: str
    nutritionist_name: Optional[str] = None
    nutritionist_email: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    pairing_code: str
    whatsapp_number: str
    whatsapp_url: str
    status: str
    notes: Optional[str] = None
    created_at: datetime
    linked_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
