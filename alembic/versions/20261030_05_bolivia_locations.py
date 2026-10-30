"""Add nullable geographic codes without guessing locations of existing businesses."""
from alembic import op
import sqlalchemy as sa

revision = '20261030_05'
down_revision = '20261029_04'
branch_labels = None
depends_on = None


def upgrade():
    for table, fields in [('tenants', [('department_code', 2)]), ('branches', [('province_code', 4), ('municipality_code', 6)])]:
        columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for name, length in fields:
            if name not in columns:
                op.add_column(table, sa.Column(name, sa.String(length), nullable=True))


def downgrade():
    raise RuntimeError('Las ubicaciones registradas no se eliminan automáticamente.')
