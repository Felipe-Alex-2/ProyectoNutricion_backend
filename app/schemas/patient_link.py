from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class GenerateLinkRequest(BaseModel):
    whatsapp_number: Optional[str] = "+591 73683564"
    tenant_id: Optional[str] = None
    notes: Optional[str] = None


class ClaimLinkRequest(BaseModel):
    pairing_code: str


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
