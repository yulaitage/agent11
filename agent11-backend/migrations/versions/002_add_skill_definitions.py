"""Add skill_definitions table

Revision ID: 002
Revises: 001
Create Date: 2026-04-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'skill_definitions',
        sa.Column('name', sa.String(), primary_key=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('code', sa.Text(), nullable=False),
        sa.Column('version', sa.String(), default='1.0.0'),
        sa.Column('category', sa.String(), nullable=True),
        sa.Column('parameters', postgresql.JSON(), nullable=True),
        sa.Column('output_schema', postgresql.JSON(), nullable=True),
        sa.Column('is_builtin', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('skill_definitions')
