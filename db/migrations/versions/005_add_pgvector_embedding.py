"""
Migration: Ativa extensão pgvector e adiciona coluna de embedding.

Permite checagem de duplicidade semântica real via embeddings.

Revision ID: 005_add_pgvector_embedding
Revises: 004_add_motivo_falha
Create Date: 2026-08-08
"""
from typing import Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005'
down_revision: Union[str, None] = '004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ativar extensão pgvector (requer superuser)
    # Verifica se a extensão pode ser criada
    conn = op.get_bind()
    result = conn.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector'"))
    has_vector = result.fetchone() is not None

    if not has_vector:
        print("WARNING: pgvector extension not available. Skipping embedding features.")
        return

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # Adicionar coluna de embedding na tabela videos_ideias
    # Usando dimensão 1536 (OpenAI text-embedding-3-small)
    # Ajustar conforme o modelo de embedding escolhido
    op.execute("""
        ALTER TABLE dados.videos_ideias
        ADD COLUMN IF NOT EXISTS embedding vector(1536)
    """)

    # Criar índice para busca de similaridade (HNSW é mais eficiente que IVFFlat para poucos dados)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_videos_ideias_embedding
        ON dados.videos_ideias
        USING hnsw (embedding vector_cosine_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS dados.idx_videos_ideias_embedding")
    op.execute("ALTER TABLE dados.videos_ideias DROP COLUMN IF EXISTS embedding")
    # Não removemos a extensão pgvector pois pode ser usada por outras tabelas
