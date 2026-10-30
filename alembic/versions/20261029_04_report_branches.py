"""Immutable branch attribution for payments and appointments."""
from alembic import op
import sqlalchemy as sa
revision = '20261029_04'
down_revision = '20261029_03'
branch_labels = None
depends_on = None

def upgrade():
    bind=op.get_bind()
    if not next(c for c in sa.inspect(bind).get_columns('generated_reports') if c['name']=='tenant_id')['nullable']:
        with op.batch_alter_table('generated_reports') as batch:
            batch.alter_column('tenant_id', existing_type=sa.String(36), nullable=True)
    for table in ['payments','appointments']:
        if 'branch_id' not in {c['name'] for c in sa.inspect(bind).get_columns(table)}:
            with op.batch_alter_table(table) as batch:
                batch.add_column(sa.Column('branch_id',sa.String(36),nullable=True))
                batch.create_foreign_key(f'fk_{table}_branch_id','branches',['branch_id'],['id'],ondelete='SET NULL')
        if f'ix_{table}_branch_id' not in {i['name'] for i in sa.inspect(bind).get_indexes(table)}:
            op.create_index(f'ix_{table}_branch_id',table,['branch_id'])
        # Backfill only when the company has exactly one branch; never guess among several.
        bind.execute(sa.text(f"UPDATE {table} SET branch_id=(SELECT MIN(id) FROM branches WHERE tenant_id={table}.tenant_id) WHERE branch_id IS NULL AND (SELECT COUNT(*) FROM branches WHERE tenant_id={table}.tenant_id)=1"))

def downgrade():
    raise RuntimeError('No se elimina la atribución histórica de sucursal automáticamente.')
