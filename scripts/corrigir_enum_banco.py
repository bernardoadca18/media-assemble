"""
Script para corrigir tipos ENUM do PostgreSQL para VARCHAR.

Problema: O banco usa tipos ENUM nativos (status_ideia_manual, prioridade_ideia)
mas o SQLAlchemy passa strings, causando erro de type mismatch.

Solução: Converter colunas para VARCHAR(20).
"""
import asyncio
import os
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

load_dotenv()


async def corrigir_enum_types():
    """Converte colunas ENUM para VARCHAR."""
    database_url = os.getenv("DATABASE_URL")

    engine = create_async_engine(database_url, echo=True)

    async with engine.begin() as conn:
        print("=" * 60)
        print("CORRIGINDO TIPOS ENUM -> VARCHAR")
        print("=" * 60)

        # 1. Verificar estrutura atual
        print("\n1. Verificando estrutura atual...")
        result = await conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dados'
            AND table_name = 'ideias_manuais'
            AND column_name IN ('status', 'prioridade')
        """))
        print("Antes:")
        for row in result:
            print(f"  - {row.column_name}: {row.data_type}")

        # 2. Criar tabela temporária
        print("\n2. Criando tabela temporária...")
        await conn.execute(text("""
            CREATE TABLE IF NOT EXISTS dados.ideias_manuais_new (
                id SERIAL PRIMARY KEY,
                nicho VARCHAR NOT NULL,
                titulo_sugerido VARCHAR NOT NULL,
                descricao_breve TEXT,
                tendencia_relacionada VARCHAR,
                prioridade VARCHAR(20) NOT NULL DEFAULT 'normal',
                status VARCHAR(20) NOT NULL DEFAULT 'pendente',
                video_id VARCHAR,
                criado_em TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))

        # 3. Copiar dados
        print("\n3. Copiando dados...")
        await conn.execute(text("""
            INSERT INTO dados.ideias_manuais_new
            (id, nicho, titulo_sugerido, descricao_breve, tendencia_relacionada,
             prioridade, status, video_id, criado_em)
            SELECT id, nicho, titulo_sugerido, descricao_breve, tendencia_relacionada,
                   prioridade::text, status::text, video_id, criado_em
            FROM dados.ideias_manuais
            ON CONFLICT (id) DO NOTHING
        """))

        # 4. Dropar tabela antiga
        print("\n4. Removendo tabela antiga...")
        await conn.execute(text("DROP TABLE IF EXISTS dados.ideias_manuais CASCADE"))

        # 5. Renomear nova tabela
        print("\n5. Renomeando tabela...")
        await conn.execute(text("""
            ALTER TABLE dados.ideias_manuais_new
            RENAME TO ideias_manuais
        """))

        # 6. Recriar índices
        print("\n6. Recriando índices...")
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_ideias_manuais_nicho_status
            ON dados.ideias_manuais (nicho, status)
        """))
        await conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_ideias_manuais_prioridade
            ON dados.ideias_manuais (prioridade)
        """))

        # 7. Verificar resultado
        print("\n7. Verificando resultado...")
        result = await conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'dados'
            AND table_name = 'ideias_manuais'
            AND column_name IN ('status', 'prioridade')
        """))
        print("Depois:")
        for row in result:
            print(f"  - {row.column_name}: {row.data_type}")

        print("\n" + "=" * 60)
        print("✅ CORREÇÃO CONCLUÍDA COM SUCESSO!")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(corrigir_enum_types())
