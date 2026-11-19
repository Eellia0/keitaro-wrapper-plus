"""Remember campaign creation requests to prevent duplicate submissions."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('creation_requests',
                    sa.Column('id', sa.String(36), primary_key=True),
                    sa.Column('payload', sa.String(), nullable=False),
                    sa.Column('result', sa.JSON(), nullable=True))


def downgrade():
    op.drop_table('creation_requests')
