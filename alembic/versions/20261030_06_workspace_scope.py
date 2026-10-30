"""Persist active workspace and immutable ownership on operational records."""
from alembic import op
import sqlalchemy as sa

revision = '20261030_06'
down_revision = '20261030_05'
branch_labels = None
depends_on = None

TABLES = ['activity_logs','nutritional_plans','chat_messages','food_records','appointments','backup_settings','backup_logs','patient_anamnesis','clinical_records','generated_reports','notifications','patient_nutritionist_links','payments','recipes','recipe_assignments','subscriptions','subscription_receipts']


def upgrade():
    bind = op.get_bind()
    for table in ['users'] + TABLES:
        columns = {c['name'] for c in sa.inspect(bind).get_columns(table)}
        fields = [('workspace_tenant_id','tenants'),('workspace_branch_id','branches')] if table == 'users' else [('tenant_id','tenants'),('branch_id','branches')]
        for name, target in fields:
            if name not in columns:
                with op.batch_alter_table(table) as batch:
                    batch.add_column(sa.Column(name, sa.String(36), nullable=True))
                    batch.create_foreign_key(f'fk_{table}_{name}', target, [name], ['id'], ondelete='SET NULL')
                    batch.create_index(f'ix_{table}_{name}', [name])
    # Only backfill unambiguous ownership; never guess among multiple branches.
    owners = {'patient_anamnesis':'patient_id','clinical_records':'patient_id','nutritional_plans':'patient_id','food_records':'patient_id','chat_messages':'patient_id','subscriptions':'user_id','subscription_receipts':'user_id'}
    for table, owner in owners.items():
        bind.execute(sa.text(f'UPDATE {table} SET tenant_id=(SELECT tenant_id FROM users WHERE id={table}.{owner}) WHERE tenant_id IS NULL'))
        bind.execute(sa.text(f'UPDATE {table} SET branch_id=(SELECT branch_id FROM users WHERE id={table}.{owner} AND users.tenant_id={table}.tenant_id) WHERE branch_id IS NULL'))
    for table in TABLES:
        bind.execute(sa.text(f'UPDATE {table} SET branch_id=(SELECT MIN(id) FROM branches WHERE tenant_id={table}.tenant_id) WHERE branch_id IS NULL AND (SELECT COUNT(*) FROM branches WHERE tenant_id={table}.tenant_id)=1'))
    bind.execute(sa.text('UPDATE recipe_assignments SET tenant_id=(SELECT tenant_id FROM recipes WHERE id=recipe_assignments.recipe_id), branch_id=(SELECT branch_id FROM recipes WHERE id=recipe_assignments.recipe_id) WHERE tenant_id IS NULL'))
    bind.execute(sa.text("UPDATE users SET workspace_branch_id=branch_id WHERE role_id NOT IN ('SUPERADMIN','CLIENTE') AND branch_id IS NOT NULL"))


def downgrade():
    raise RuntimeError('No se elimina automáticamente la atribución histórica por sucursal.')
