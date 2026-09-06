import random
import string
import urllib.parse
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.patient_link import PatientNutritionistLink
from app.models.user import User
from app.schemas.patient_link import GenerateLinkRequest, PatientLinkResponse
from app.core.exceptions import BadRequestException, NotFoundException


class PatientLinkService:
    @staticmethod
    def _generate_code(length: int = 5) -> str:
        digits = "".join(random.choices(string.digits, k=length))
        return f"NUTRI-{digits}"

    @staticmethod
    def _build_whatsapp_url(phone: str, code: str) -> str:
        # Clean phone: only keep numbers
        cleaned_phone = "".join(filter(str.isdigit, phone))
        message = (
            f"¡Hola! Te comparto tu código de vinculación en NutriSalud: *{code}*\n\n"
            f"Ingresa este código en tu aplicación para conectar tu cuenta con tu especialista de nutrición."
        )
        encoded_message = urllib.parse.quote(message)
        return f"https://wa.me/{cleaned_phone}?text={encoded_message}"

    @classmethod
    def generate_link(
        cls,
        db: Session,
        nutritionist_id: str,
        data: GenerateLinkRequest,
    ) -> PatientLinkResponse:
        # Check nutritionist exists
        nutri = db.query(User).filter(User.id == nutritionist_id).first()
        if not nutri:
            raise NotFoundException("Nutricionista no encontrado")

        # Generate unique code
        code = None
        for _ in range(10):
            candidate = cls._generate_code()
            if not db.query(PatientNutritionistLink).filter(PatientNutritionistLink.pairing_code == candidate).first():
                code = candidate
                break
        if not code:
            code = f"NUTRI-{int(datetime.now().timestamp()) % 100000}"

        phone = data.whatsapp_number or "+591 73683564"
        link = PatientNutritionistLink(
            nutritionist_id=nutritionist_id,
            tenant_id=data.tenant_id or nutri.tenant_id,
            pairing_code=code,
            whatsapp_number=phone,
            status="PENDING",
            notes=data.notes,
        )
        db.add(link)
        db.commit()
        db.refresh(link)

        return cls._format_response(link, nutri, None)

    @classmethod
    def list_links(
        cls,
        db: Session,
        nutritionist_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> List[PatientLinkResponse]:
        query = db.query(PatientNutritionistLink)
        if nutritionist_id:
            query = query.filter(PatientNutritionistLink.nutritionist_id == nutritionist_id)
        if tenant_id:
            query = query.filter(PatientNutritionistLink.tenant_id == tenant_id)

        links = query.order_by(PatientNutritionistLink.created_at.desc()).all()
        result = []
        for l in links:
            nutri = db.query(User).filter(User.id == l.nutritionist_id).first()
            patient = db.query(User).filter(User.id == l.patient_id).first() if l.patient_id else None
            result.append(cls._format_response(l, nutri, patient))
        return result

    @classmethod
    def claim_link(
        cls,
        db: Session,
        patient_id: str,
        pairing_code: str,
    ) -> PatientLinkResponse:
        clean_code = pairing_code.strip().upper()
        link = (
            db.query(PatientNutritionistLink)
            .filter(PatientNutritionistLink.pairing_code == clean_code)
            .first()
        )
        if not link:
            raise NotFoundException("El código de vinculación no existe")

        if link.status != "PENDING":
            raise BadRequestException(f"Este código ya ha sido utilizado (estado: {link.status})")

        patient = db.query(User).filter(User.id == patient_id).first()
        if not patient:
            raise NotFoundException("Paciente no encontrado")

        link.patient_id = patient_id
        link.status = "LINKED"
        link.linked_at = datetime.now(timezone.utc)
        if link.tenant_id and not patient.tenant_id:
            patient.tenant_id = link.tenant_id

        db.commit()
        db.refresh(link)

        nutri = db.query(User).filter(User.id == link.nutritionist_id).first()
        return cls._format_response(link, nutri, patient)

    @classmethod
    def get_my_nutritionist(
        cls,
        db: Session,
        patient_id: str,
    ) -> Optional[PatientLinkResponse]:
        link = (
            db.query(PatientNutritionistLink)
            .filter(
                PatientNutritionistLink.patient_id == patient_id,
                PatientNutritionistLink.status == "LINKED",
            )
            .order_by(PatientNutritionistLink.linked_at.desc())
            .first()
        )
        if not link:
            return None
        nutri = db.query(User).filter(User.id == link.nutritionist_id).first()
        patient = db.query(User).filter(User.id == link.patient_id).first()
        return cls._format_response(link, nutri, patient)

    @classmethod
    def _format_response(
        cls,
        link: PatientNutritionistLink,
        nutri: Optional[User],
        patient: Optional[User],
    ) -> PatientLinkResponse:
        wa_url = cls._build_whatsapp_url(link.whatsapp_number, link.pairing_code)
        tenant_name = link.tenant.name if link.tenant else None
        return PatientLinkResponse(
            id=link.id,
            tenant_id=link.tenant_id,
            tenant_name=tenant_name,
            nutritionist_id=link.nutritionist_id,
            nutritionist_name=nutri.full_name if nutri else "Especialista",
            nutritionist_email=nutri.email if nutri else None,
            patient_id=link.patient_id,
            patient_name=patient.full_name if patient else None,
            pairing_code=link.pairing_code,
            whatsapp_number=link.whatsapp_number,
            whatsapp_url=wa_url,
            status=link.status,
            notes=link.notes,
            created_at=link.created_at,
            linked_at=link.linked_at,
        )
