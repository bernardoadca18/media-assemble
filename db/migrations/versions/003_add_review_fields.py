"""
Migration: Adiciona campos de revisão na tabela roteiros.

Campos adicionados:
- status_revisao: pendente, aprovado, rejeitado
- revisado_em: timestamp da revisão
"""
from alembic import op
import sqlalchemy as sa


def upgrade():
    # Adiciona coluna status_revisao com valor padrão 'pendente'
    op.add_column(
        'roteiros',
        sa.Column('status_revisao', sa.String(), nullable=False, server_default='pendente'),
        schema='dados'
    )

    # Adiciona coluna revisado_em (nullable)
    op.add_column(
        'roteiros',
        sa.Column('revisado_em', sa.DateTime(timezone=True), nullable=True),
        schema='dados'
    )


def downgrade():
    op.drop_column('roteiros', 'revisado_em', schema='dados')
    op.drop_column('roteiros', 'status_revisao', schema='dados')
