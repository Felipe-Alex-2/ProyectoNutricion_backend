from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.models.clinical import PatientAnamnesis, ClinicalRecord
from app.models.activity_log import ActivityLog
from app.schemas.clinical import (
    AnamnesisCreateOrUpdate,
    AnamnesisResponse,
    ClinicalRecordCreateOrUpdate,
    ClinicalRecordResponse,
)

router = APIRouter(prefix="/clinical", tags=["Clínica y Anamnesis"])


# =====================================================================
# 1. ANAMNESIS (LLENADO POR PACIENTE EN MÓVIL / CONSULTA EN WEB)
# =====================================================================

@router.get("/anamnesis/me", response_model=Optional[AnamnesisResponse])
def get_my_anamnesis(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El paciente consulta su propia anamnesis registrada desde el Móvil o Web."""
    anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == current_user.id).first()
    return anamnesis


@router.post("/anamnesis/me", response_model=AnamnesisResponse, status_code=status.HTTP_200_OK)
def save_my_anamnesis(
    data: AnamnesisCreateOrUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El paciente guarda o actualiza sus antecedentes y estilo de vida (Móvil)."""
    anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == current_user.id).first()

    payload = data.model_dump(exclude_unset=True)
    if not anamnesis:
        anamnesis = PatientAnamnesis(
            patient_id=current_user.id,
            tenant_id=current_user.tenant_id,
            **payload,
        )
        db.add(anamnesis)
        action = "ANAMNESIS_CREADA"
        desc = "El paciente completó su ficha inicial de anamnesis."
    else:
        for key, value in payload.items():
            setattr(anamnesis, key, value)
        action = "ANAMNESIS_ACTUALIZADA"
        desc = "El paciente actualizó sus datos de anamnesis y salud."

    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action=action,
        description=desc,
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    db.refresh(anamnesis)
    return anamnesis


@router.get("/patients/{patient_id}/anamnesis", response_model=Optional[AnamnesisResponse])
def get_patient_anamnesis_by_staff(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Nutricionistas y Administradores consultan la anamnesis del paciente en la Web."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso no autorizado.")

    patient = db.query(User).filter(User.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")

    # Validar aislamiento de clínica si no es ADMIN_SAAS
    if current_user.role_id == "ADMIN_ORGANIZATION" and patient.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Paciente no pertenece a tu clínica.")

    anamnesis = db.query(PatientAnamnesis).filter(PatientAnamnesis.patient_id == patient_id).first()

    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="ANAMNESIS_CONSULTADA",
        description=f"El especialista consultó la anamnesis del paciente '{patient.full_name}'.",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()

    return anamnesis


# =====================================================================
# 2. HISTORIAL CLÍNICO (NOTAS Y DIAGNÓSTICO EN WEB POR EL NUTRICIONISTA)
# =====================================================================

@router.get("/patients/{patient_id}/records", response_model=List[ClinicalRecordResponse])
def get_patient_clinical_records(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consultar las notas diagnósticas y evolución clínica del paciente (Web)."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        if current_user.id != patient_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso denegado.")

    records = (
        db.query(ClinicalRecord)
        .filter(ClinicalRecord.patient_id == patient_id)
        .order_by(ClinicalRecord.created_at.desc())
        .all()
    )
    return records


@router.post("/patients/{patient_id}/records", response_model=ClinicalRecordResponse, status_code=status.HTTP_201_CREATED)
def create_clinical_record(
    patient_id: str,
    data: ClinicalRecordCreateOrUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """El Nutricionista o Administrador registra diagnóstico o nota de evolución clínica (Web)."""
    if current_user.role_id not in ["ADMIN_SAAS", "ADMIN_ORGANIZATION", "NUTRICIONISTA"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo profesionales de salud pueden asentar notas clínicas.")

    patient = db.query(User).filter(User.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paciente no encontrado.")

    record = ClinicalRecord(
        patient_id=patient.id,
        nutritionist_id=current_user.id,
        tenant_id=patient.tenant_id or current_user.tenant_id,
        diagnosis=data.diagnosis,
        evolution_notes=data.evolution_notes,
        clinical_goals=data.clinical_goals,
    )
    db.add(record)

    log = ActivityLog(
        user_id=current_user.id,
        user_email=current_user.email,
        user_name=current_user.full_name,
        action="HISTORIAL_CLINICO_ACTUALIZADO",
        description=f"Se asentó diagnóstico clínico para '{patient.full_name}'.",
        category="CLINICAL",
    )
    db.add(log)
    db.commit()
    db.refresh(record)
    return record
