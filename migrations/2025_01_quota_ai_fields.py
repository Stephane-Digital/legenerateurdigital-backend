"""Add AI quota fields to users table - LGD 2025"""

from alembic import op
import sqlalchemy as sa

# Identifiants migration
revision = '2025_01_quota_ai_fields'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ===== Ajout des colonnes IA =====
    op.add_column('users', sa.Column('plan', sa.String(length=50), nullable=False, server_default='essential'))
    op.add_column('users', sa.Column('ai_usage_weekly', sa.Float(), nullable=False, server_default='0'))
    op.add_column('users', sa.Column('ai_usage_limit', sa.Integer(), nullable=False, server_default='15'))
    op.add_column('users', sa.Column('ai_last_reset', sa.DateTime(), nullable=True))


def downgrade():
    # ===== Suppression des colonnes IA =====
    op.drop_column('users', 'plan')
    op.drop_column('users', 'ai_usage_weekly')
    op.drop_column('users', 'ai_usage_limit')
    op.drop_column('users', 'ai_last_reset')
