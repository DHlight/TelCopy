"""add bot_token column to telegram_accounts

Revision ID: add_bot_token_001
Revises: 
Create Date: 2025-05-07 12:40:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_bot_token_001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('telegram_accounts', sa.Column('bot_token', sa.String(), nullable=True))

def downgrade():
    op.drop_column('telegram_accounts', 'bot_token')
