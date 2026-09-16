from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.models.user import User
from app.models.patient_link import PatientNutritionistLink
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


class UserService:
    @staticmethod
    def get_by_id(db: Session, user_id: str) -> Optional[User]:
        """Fetch user by primary key ID."""
        return db.query(User).filter(User.id == user_id).first()

    @staticmethod
    def get_by_email(db: Session, email: str) -> Optional[User]:
        """Fetch user by email address."""
        return db.query(User).filter(User.email == email.lower().strip()).first()

    @staticmethod
    def create(db: Session, obj_in: UserCreate, role_id: Optional[str] = None) -> User:
        """Create a new user with hashed password."""
        db_obj = User(
            email=obj_in.email.lower().strip(),
            hashed_password=get_password_hash(obj_in.password),
            full_name=obj_in.full_name.strip(),
            phone=obj_in.phone.strip() if obj_in.phone else None,
            role_id=role_id or obj_in.role_id or "ADMIN_SAAS",
            tenant_id=obj_in.tenant_id,
            is_active=True,
            is_verified=False,
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def update(db: Session, db_obj: User, obj_in: UserUpdate) -> User:
        """Update an existing user."""
        if obj_in.full_name is not None:
            db_obj.full_name = obj_in.full_name.strip()
        if obj_in.email is not None:
            db_obj.email = obj_in.email.lower().strip()
        if obj_in.phone is not None:
            db_obj.phone = obj_in.phone.strip() if obj_in.phone else None
        if obj_in.password is not None:
            db_obj.hashed_password = get_password_hash(obj_in.password)
        if obj_in.role_id is not None:
            db_obj.role_id = obj_in.role_id
        if obj_in.tenant_id is not None:
            db_obj.tenant_id = obj_in.tenant_id
        if obj_in.is_active is not None:
            db_obj.is_active = obj_in.is_active
        if obj_in.developer_key is not None:
            raw_key = obj_in.developer_key.strip()
            if raw_key:
                db_obj.developer_key_hash = get_password_hash(raw_key)
            else:
                db_obj.developer_key_hash = None

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    @staticmethod
    def list_patients(
        db: Session,
        nutritionist_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        search: Optional[str] = None,
        is_active: Optional[bool] = None,
        limit: int = 200,
    ) -> List[dict]:
        """Obtiene la lista detallada de clientes/pacientes para administración y nutricionistas."""
        query = db.query(User).filter(User.role_id == "CLIENTE")

        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)

        if is_active is not None:
            query = query.filter(User.is_active == is_active)

        if search:
            s = f"%{search.strip().lower()}%"
            query = query.filter(
                or_(
                    User.full_name.ilike(s),
                    User.email.ilike(s),
                    User.phone.ilike(s),
                )
            )

        patients = query.order_by(User.created_at.desc()).limit(limit).all()

        results = []
        for p in patients:
            # Buscar vinculación activa
            link = (
                db.query(PatientNutritionistLink)
                .filter(PatientNutritionistLink.patient_id == p.id)
                .order_by(PatientNutritionistLink.created_at.desc())
                .first()
            )
            nutri_name = None
            if link and link.nutritionist_id:
                nutri = db.query(User).filter(User.id == link.nutritionist_id).first()
                nutri_name = nutri.full_name if nutri else None

            results.append({
                "id": p.id,
                "full_name": p.full_name,
                "email": p.email,
                "phone": p.phone,
                "is_active": p.is_active,
                "tenant_id": p.tenant_id,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "linked_status": link.status if link else "UNLINKED",
                "nutritionist_name": nutri_name,
                "pairing_code": link.pairing_code if link else None,
            })
        return results

    @staticmethod
    def deactivate_patient(db: Session, patient_id: str) -> bool:
        """Desactiva un cliente y cancela o desvincula sus enlaces activos."""
        patient = db.query(User).filter(User.id == patient_id, User.role_id == "CLIENTE").first()
        if not patient:
            return False

        patient.is_active = False

        # Desvincular links
        links = db.query(PatientNutritionistLink).filter(PatientNutritionistLink.patient_id == patient_id).all()
        for link in links:
            link.status = "UNLINKED"

        db.commit()
        return True
