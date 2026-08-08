"""
Migration: Adiciona campo motivo_falha na tabela execucoes_pipeline.

Permite registrar a mensagem de erro detalhada quando uma execução falha,
facilitando debugging e retomada manual.

Revision ID: 004_add_motivo_falha
Revises: 003_add_review_fields
Create Date: 2026-08-08
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_motivo_falha'
down_revision: str = '003_add_review_fields'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Adiciona coluna motivo_falha (texto livre para mensagem de erro)
    op.add_column(
        'execucoes_pipeline',
        sa.Column('motivo_falha', sa.Text(), nullable=True),
        schema='dados'
    )


def downgrade() -> None:
    op.drop_column('execucoes_pipeline', 'motivo_falha', schema='dados')
