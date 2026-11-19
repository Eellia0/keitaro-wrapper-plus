"""Store editor drafts and archived offer links."""
from alembic import op
import sqlalchemy as sa
revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('campaign_drafts', sa.Column('id', sa.Integer(), primary_key=True), sa.Column('revision', sa.Integer(), nullable=False), sa.Column('data', sa.JSON(), nullable=False))

def downgrade():
    op.drop_table('campaign_drafts')
