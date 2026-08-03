"""add roteiros table

Revision ID: 002
Revises: 001
Create Date: 2026-08-03

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002'
down_revision = '001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Criar tabela roteiros no schema dados
    op.execute("CREATE SCHEMA IF NOT EXISTS dados")

    op.create_table(
        'roteiros',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('video_id', sa.String(), nullable=False),
        sa.Column('nicho', sa.String(), nullable=False),
        sa.Column('titulo_sugerido', sa.String(), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('criado_em', sa.DateTime(timezone=True), server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('video_id'),
        schema='dados'
    )

    # Criar índice para video_id
    op.create_index(
        op.f('ix_dados_roteiros_video_id'),
        'roteiros',
        ['video_id'],
        unique=False,
        schema='dados'
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_dados_roteiros_video_id'), table_name='roteiros', schema='dados')
    op.drop_table('roteiros', schema='dados')
