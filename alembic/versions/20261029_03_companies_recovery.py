"""Company branches, operational recovery, saved reports and superadmin."""
from alembic import op
import sqlalchemy as sa
from datetime import datetime, timezone

revision = '20261029_03'
down_revision = '20261012_02'
branch_labels = None
depends_on = None

def upgrade():
    from app.models.company import Branch, CompanyAdministrator
    from app.models.generated_report import GeneratedReport
    bind = op.get_bind()
    for table in (Branch.__table__, CompanyAdministrator.__table__, GeneratedReport.__table__): table.create(bind, checkfirst=True)
    additions = [
        ('users', sa.Column('branch_id', sa.String(36), nullable=True), 'branches', 'SET NULL'),
        ('activity_logs', sa.Column('tenant_id', sa.String(36), nullable=True), 'tenants', 'SET NULL'),
        ('appointments', sa.Column('completed_at', sa.DateTime(), nullable=True), None, None),
    ]
    for table, column, target, ondelete in additions:
        inspector = sa.inspect(bind)
        if column.name not in {c['name'] for c in inspector.get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(column)
                if target:
                    batch.create_foreign_key(f'fk_{table}_{column.name}', target, [column.name], ['id'], ondelete=ondelete)
        if target and f'ix_{table}_{column.name}' not in {i['name'] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(f'ix_{table}_{column.name}', table, [column.name])
    roles = sa.table('roles', sa.column('id'),sa.column('name'),sa.column('description'),sa.column('platform'),sa.column('created_at'))
    if not bind.execute(sa.select(roles.c.id).where(roles.c.id == 'SUPERADMIN')).first():
        bind.execute(roles.insert().values(id='SUPERADMIN', name='Superadmin', description='Administración de la plataforma y creación de empresas', platform='Web', created_at=datetime.now(timezone.utc)))
    bind.execute(sa.text("UPDATE roles SET name='Administrador de empresa' WHERE id='ADMIN_ORGANIZATION'"))
    legacy_permissions = bind.execute(sa.text("SELECT permission_id FROM role_permissions WHERE role_id='ADMIN_SAAS'")).scalars().all()
    for permission in legacy_permissions:
        if not bind.execute(sa.text("SELECT 1 FROM role_permissions WHERE role_id='SUPERADMIN' AND permission_id=:permission"), {'permission': permission}).first():
            bind.execute(sa.text("INSERT INTO role_permissions(role_id,permission_id) VALUES ('SUPERADMIN',:permission)"), {'permission': permission})
    # Only previously privileged global administrators become superadmins.
    bind.execute(sa.text("UPDATE users SET role_id='SUPERADMIN', session_version=session_version+1 WHERE role_id='ADMIN_SAAS'"))
    bind.execute(sa.text('UPDATE activity_logs SET ip_address=NULL'))
    bind.execute(sa.text('UPDATE activity_logs SET tenant_id=(SELECT tenant_id FROM users WHERE users.id=activity_logs.user_id) WHERE tenant_id IS NULL'))
    bind.execute(sa.text("DELETE FROM activity_logs WHERE action IN ('NAVEGACION','ACCESO','LOGIN','LOGOUT','CAMBIO_TEMA')"))
    companies = bind.execute(sa.text('SELECT id,name FROM tenants')).mappings().all()
    import uuid
    for company in companies:
        branch = bind.execute(sa.select(Branch.__table__.c.id).where(Branch.__table__.c.tenant_id == company['id'])).scalar()
        if not branch:
            branch = str(uuid.uuid4())
            bind.execute(Branch.__table__.insert().values(id=branch, tenant_id=company['id'], name='Sucursal principal',code='PRINCIPAL',is_active=True,created_at=datetime.now(timezone.utc)))
        bind.execute(sa.text('UPDATE users SET branch_id=:branch WHERE tenant_id=:company AND branch_id IS NULL'), {'branch':branch,'company':company['id']})
        admin = bind.execute(sa.text("SELECT id FROM users WHERE tenant_id=:company AND role_id='ADMIN_ORGANIZATION' ORDER BY created_at LIMIT 1"), {'company':company['id']}).scalar()
        if admin and not bind.execute(sa.select(CompanyAdministrator.__table__.c.tenant_id).where(CompanyAdministrator.__table__.c.tenant_id == company['id'])).first():
            bind.execute(CompanyAdministrator.__table__.insert().values(tenant_id=company['id'],user_id=admin))

def downgrade():
    raise RuntimeError('No se eliminan automáticamente empresas, reportes ni datos de recuperación.')
