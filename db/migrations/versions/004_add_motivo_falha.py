"""
Migration: Adiciona campo motivo_falha na tabela execucoes_pipeline.

Permite registrar a mensagem de erro detalhada quando uma execução falha,
facilitando debugging e retomada manual.

Revision ID: 004_add_motivo_falha
Revises: 003_add_review_fields
Create Date: 2026-08-08
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # Adiciona coluna motivo_falha (texto livre para mensagem de erro)
    op.add_column(
        'execucoes_pipeline',
        sa.Column('motivo_falha', sa.Text(), nullable=True),
        schema='dados'
    )


def downgrade() -> None:
    op.drop_column('execucoes_pipeline', 'motivo_falha', schema='dados')
