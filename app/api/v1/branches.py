from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.company import Branch
from app.models.tenant import Tenant
from app.models.user import User
from app.core.authorization import ADMIN_ROLES, require_role, require_tenant
from app.core.exceptions import BadRequestException, NotFoundException

router = APIRouter(prefix='/branches', tags=['Sucursales'])

class BranchCreate(BaseModel):
    tenant_id: str
    name: str = Field(min_length=2, max_length=250)
    code: str = Field(min_length=2, max_length=50)
    address: Optional[str] = Field(None, max_length=255)

class BranchOut(BranchCreate):
    id: str
    is_active: bool
    model_config = ConfigDict(from_attributes=True)

@router.get('/public', response_model=list[BranchOut])
def public_branches(tenant_id: str, db: Session = Depends(get_db)):
    return db.query(Branch).join(Tenant, Tenant.id == Branch.tenant_id).filter(Branch.tenant_id == tenant_id, Branch.is_active.is_(True), Tenant.is_active.is_(True)).all()

@router.get('', response_model=list[BranchOut])
def list_branches(tenant_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = tenant_id if user.role_id == 'SUPERADMIN' else user.tenant_id
    if user.role_id != 'SUPERADMIN': require_tenant(user, company)
    query = db.query(Branch)
    return query.filter(Branch.tenant_id == company).all() if company else query.all()

@router.post('', response_model=BranchOut, status_code=201)
def create_branch(data: BranchCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    require_role(user, ADMIN_ROLES); require_tenant(user, data.tenant_id)
    if not db.get(Tenant, data.tenant_id): raise NotFoundException('Empresa no encontrada.')
    name = data.name.strip(); code = data.code.strip().upper()
    if len(name) < 2 or len(code) < 2: raise BadRequestException('Nombre y código son obligatorios.')
    if db.query(Branch).filter_by(tenant_id=data.tenant_id, code=code).first(): raise BadRequestException('Ese código de sucursal ya existe en la empresa.')
    branch = Branch(tenant_id=data.tenant_id, name=name, code=code, address=data.address)
    db.add(branch); db.commit(); db.refresh(branch); return branch
