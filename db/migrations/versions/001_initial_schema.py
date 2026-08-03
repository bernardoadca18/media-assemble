"""Schema inicial com tabelas videos_ideias e execucoes_pipeline

Revision ID: 001_initial
Revises:
Create Date: 2026-08-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cria o schema 'dados' se não existir
    op.execute("CREATE SCHEMA IF NOT EXISTS dados")

    # Tabela videos_ideias (compatível com estrutura do fluxo n8n original)
    op.create_table(
        'videos_ideias',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('topico', sa.String(), nullable=False),
        sa.Column('titulo_sugerido', sa.String(), nullable=False),
        sa.Column('descricao_breve', sa.Text(), nullable=True),
        sa.Column('nicho', sa.String(), nullable=False, server_default='cultura_pop'),
        sa.Column('status', sa.String(), nullable=False, server_default='pendente'),
        sa.Column('data_criacao', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        schema='dados'
    )

    # Índice para consultas por nicho e data
    op.create_index(
        'ix_videos_ideias_nicho_data',
        'videos_ideias',
        ['nicho', 'data_criacao'],
        schema='dados'
    )

    # Tabela execucoes_pipeline (nova, para rastreabilidade do pipeline Python)
    op.create_table(
        'execucoes_pipeline',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nicho', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('inicio_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('fim_em', sa.DateTime(timezone=True), nullable=True),
        sa.Column('erro', sa.Text(), nullable=True),
        sa.Column('roteiro_json', sa.JSON(), nullable=True),
        sa.Column('caminho_video_final', sa.String(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='dados'
    )

    # Índice para consultas por nicho e status
    op.create_index(
        'ix_execucoes_pipeline_nicho_status',
        'execucoes_pipeline',
        ['nicho', 'status'],
        schema='dados'
    )


def downgrade() -> None:
    op.drop_index('ix_execucoes_pipeline_nicho_status', table_name='execucoes_pipeline', schema='dados')
    op.drop_table('execucoes_pipeline', schema='dados')

    op.drop_index('ix_videos_ideias_nicho_data', table_name='videos_ideias', schema='dados')
    op.drop_table('videos_ideias', schema='dados')

    # Opcional: remover o schema (cuidado em produção)
    # op.execute("DROP SCHEMA IF EXISTS dados CASCADE")
