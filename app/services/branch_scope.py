from app.models.company import Branch
from app.core.exceptions import BadRequestException

def operation_branch(db, company, requested=None, default=None):
    from app.core.workspace import current
    scope = current(db)
    if scope and scope.staff and scope.branch_id:
        if requested and requested != scope.branch_id:
            raise BadRequestException('El cobro debe registrarse en la sucursal activa.')
        if company != scope.tenant_id:
            raise BadRequestException('La empresa no coincide con el espacio activo.')
        requested = scope.branch_id
    candidate=requested or default
    if candidate:
        branch=db.get(Branch,candidate)
        if not branch or branch.tenant_id!=company or not branch.is_active:
            raise BadRequestException('La sucursal no está disponible en la empresa seleccionada.')
        return branch.id
    branches=db.query(Branch).filter_by(tenant_id=company,is_active=True).limit(2).all()
    if len(branches)==1:return branches[0].id
    if len(branches)>1:raise BadRequestException('Selecciona una sucursal para registrar la operación.')
    return None  # Compatibility with legacy data before company setup.
