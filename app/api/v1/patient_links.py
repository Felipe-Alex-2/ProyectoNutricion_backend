from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.patient_link import (
    GenerateLinkRequest,
    ClaimLinkRequest,
    PatientLinkResponse,
)
from app.services.patient_link_service import PatientLinkService

router = APIRouter(prefix="/patient-links", tags=["Vinculación Paciente - WhatsApp"])


@router.post("/generate", response_model=PatientLinkResponse, status_code=status.HTTP_201_CREATED)
def generate_link(
    data: GenerateLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Nutritionist is the current user (or admin generating for themselves)
    return PatientLinkService.generate_link(db, nutritionist_id=current_user.id, data=data)


@router.get("", response_model=List[PatientLinkResponse])
def list_links(
    tenant_id: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Nutritionist can see their own or all for SaaS Admin
    nutri_id = None if current_user.role_id == "ADMIN_SAAS" else current_user.id
    return PatientLinkService.list_links(db, nutritionist_id=nutri_id, tenant_id=tenant_id)


@router.post("/claim", response_model=PatientLinkResponse)
def claim_link(
    data: ClaimLinkRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PatientLinkService.claim_link(db, patient_id=current_user.id, pairing_code=data.pairing_code)


@router.get("/my-nutritionist", response_model=Optional[PatientLinkResponse])
def get_my_nutritionist(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return PatientLinkService.get_my_nutritionist(db, patient_id=current_user.id)
