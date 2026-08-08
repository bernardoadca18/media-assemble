"""
Migration: Adiciona tabela dados.ideias_manuais.

Subfase 8.8 — Painel de controle editorial.

Campos:
- id: PK
- nicho: nicho do canal
- titulo_sugerido: título da ideia manual
- descricao_breve: descrição opcional
- tendencia_relacionada: tendência opcional que inspirou a ideia
- prioridade: 'alta' ou 'normal'
- status: 'pendente', 'usada', 'descartada'
- video_id: ID do vídeo gerado (quando status='usada')
- criado_em: timestamp de criação
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ENUM

# Revision IDs
revision = "006_add_ideias_manuais"
down_revision = "005_add_pgvector_embedding"
branch_labels = None
depends_on = None


def upgrade():
    # Criar enum para prioridade
    prioridade_enum = ENUM("alta", "normal", name="prioridade_ideia", create_type=False)
    prioridade_enum.create(op.get_bind(), checkfirst=True)

    # Criar enum para status
    status_enum = ENUM("pendente", "usada", "descartada", name="status_ideia_manual", create_type=False)
    status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "ideias_manuais",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("nicho", sa.String(), nullable=False),
        sa.Column("titulo_sugerido", sa.String(), nullable=False),
        sa.Column("descricao_breve", sa.Text(), nullable=True),
        sa.Column("tendencia_relacionada", sa.String(), nullable=True),
        sa.Column("prioridade", prioridade_enum, nullable=False, server_default="normal"),
        sa.Column("status", status_enum, nullable=False, server_default="pendente"),
        sa.Column("video_id", sa.String(), nullable=True),
        sa.Column("criado_em", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        schema="dados",
    )

    # Índices para consultas frequentes
    op.create_index("ix_ideias_manuais_nicho_status", "ideias_manuais", ["nicho", "status"], schema="dados")
    op.create_index("ix_ideias_manuais_prioridade", "ideias_manuais", ["prioridade"], schema="dados")


def downgrade():
    op.drop_index("ix_ideias_manuais_prioridade", table_name="ideias_manuais", schema="dados")
    op.drop_index("ix_ideias_manuais_nicho_status", table_name="ideias_manuais", schema="dados")
    op.drop_table("ideias_manuais", schema="dados")

    # Remover enums
    op.execute("DROP TYPE IF EXISTS prioridade_ideia")
    op.execute("DROP TYPE IF EXISTS status_ideia_manual")
