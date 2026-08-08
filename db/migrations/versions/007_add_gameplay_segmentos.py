"""add gameplay_segmentos table

Revision ID: 007_add_gameplay_segmentos
Revises: 006_add_ideias_manuais
Create Date: 2026-08-08

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '007_add_gameplay_segmentos'
down_revision = '006_add_ideias_manuais'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'gameplay_segmentos',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('jogo_origem', sa.String(), nullable=False),
        sa.Column('caminho_arquivo', sa.String(), nullable=False),
        sa.Column('duracao_segundos', sa.Float(), nullable=False),
        sa.Column('score_movimento', sa.Float(), nullable=False),
        sa.Column('faixa_intensidade', sa.String(), nullable=False),
        sa.Column('hash_conteudo', sa.String(length=32), nullable=False),
        sa.Column('usado_em', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('caminho_arquivo'),
        sa.UniqueConstraint('hash_conteudo'),
        schema='dados',
    )

    # Índices para consultas comuns
    op.create_index('ix_dados_gameplay_segmentos_jogo', 'gameplay_segmentos', ['jogo_origem'], schema='dados')
    op.create_index('ix_dados_gameplay_segmentos_intensidade', 'gameplay_segmentos', ['faixa_intensidade'], schema='dados')
    op.create_index('ix_dados_gameplay_segmentos_score', 'gameplay_segmentos', ['score_movimento'], schema='dados')


def downgrade() -> None:
    op.drop_index('ix_dados_gameplay_segmentos_score', table_name='gameplay_segmentos', schema='dados')
    op.drop_index('ix_dados_gameplay_segmentos_intensidade', table_name='gameplay_segmentos', schema='dados')
    op.drop_index('ix_dados_gameplay_segmentos_jogo', table_name='gameplay_segmentos', schema='dados')
    op.drop_table('gameplay_segmentos', schema='dados')
