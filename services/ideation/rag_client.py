"""
FASE 1 — Cliente RAG para checagem de duplicidade de temas.

Consulta o histórico de vídeos já publicados/criados (armazenado com
embeddings no Postgres via `pgvector`) para evitar que o agente de ideação
sugira temas repetidos ou semanticamente muito próximos de vídeos anteriores.

Isto substitui e melhora a lógica que existia embutida no prompt do fluxo
n8n original (`$items("Execute a SQL query").map(...)`), que apenas listava
títulos textualmente — aqui a checagem passa a ser semântica (embedding),
não apenas por correspondência exata de string.
"""
import logging
import os

from db.models import buscar_titulos_recentes_db
from db.session import AsyncSessionLocal
from sqlalchemy import text
from utils.litellm_client import generate_embedding

logger = logging.getLogger("services.ideation.rag_client")

# Limiar de similaridade para considerar duplicata (0.0 a 1.0)
# Configurável via variável de ambiente, padrão 0.85
LIMIAR_DUPLICIDADE_SEMANTICA = float(os.getenv("LIMIAR_DUPLICIDADE_SEMANTICA", "0.85"))


async def buscar_titulos_recentes(nicho: str, limite: int = 30) -> list[str]:
    """
    Consulta a tabela `dados.videos_ideias` e retorna os `titulo_sugerido`
    mais recentes para o nicho, ordenados por `data_criacao DESC`.

    Equivalente direto ao nó "Execute a SQL query" do fluxo n8n original.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite: Número máximo de títulos a retornar

    Returns:
        Lista de títulos já utilizados, para evitar repetição no prompt
    """
    try:
        titulos = await buscar_titulos_recentes_db(nicho=nicho, limite=limite)
        logger.info(
            "buscar_titulos_recentes.sucesso",
            extra={"nicho": nicho, "total": len(titulos)}
        )
        return titulos
    except Exception as e:
        logger.error(
            "buscar_titulos_recentes.erro",
            extra={"nicho": nicho, "erro": str(e)}
        )
        return []


async def checar_duplicidade_semantica(
    titulo_candidato: str,
    nicho: str,
    limiar: float | None = None,
) -> bool:
    """
    Checa se o título candidato é semanticamente similar a títulos já existentes
    no mesmo nicho, usando embeddings vetoriais via pgvector.

    Args:
        titulo_candidato: Título a ser verificado
        nicho: Nicho do canal (para filtrar busca)
        limiar: Limiar de similaridade de cosseno (0.0 a 1.0). Se None, usa
                variável de ambiente LIMIAR_DUPLICIDADE_SEMANTICA ou 0.85

    Returns:
        True se encontrar título similar acima do limiar (duplicata), False caso contrário

    Raises:
        Exception: Se falhar ao gerar embedding ou consultar banco (logger captura)
    """
    limiar_efetivo = limiar if limiar is not None else LIMIAR_DUPLICIDADE_SEMANTICA

    try:
        # 1. Gerar embedding do título candidato
        embedding_candidato = await generate_embedding(
            text=titulo_candidato,
            operacao="duplicidade_semantica",
            nicho=nicho,
        )

        # 2. Buscar títulos mais similares no mesmo nicho via pgvector
        # Similaridade de cosseno: 1 - distancia_cosseno
        # pgvector usa <=> para distancia de cosseno
        async with AsyncSessionLocal() as session:
            # Converter lista para string no formato de array do Postgres
            embedding_str = "[" + ",".join(str(v) for v in embedding_candidato) + "]"

            query = text("""
                SELECT
                    titulo_sugerido,
                    1 - (embedding <=> :embedding::vector) as similaridade
                FROM dados.videos_ideias
                WHERE nicho = :nicho
                  AND embedding IS NOT NULL
                ORDER BY embedding <=> :embedding::vector
                LIMIT 5
            """)

            result = await session.execute(
                query,
                {"embedding": embedding_str, "nicho": nicho}
            )
            similares = result.fetchall()

        # 3. Verificar se algum ultrapassa o limiar
        for titulo, similaridade in similares:
            logger.info(
                "checar_duplicidade_semantica.comparacao",
                extra={
                    "titulo_candidato": titulo_candidato,
                    "titulo_existente": titulo,
                    "similaridade": float(similaridade),
                    "limiar": limiar_efetivo,
                    "nicho": nicho,
                }
            )

            if float(similaridade) >= limiar_efetivo:
                logger.warning(
                    "checar_duplicidade_semantica.duplicata_encontrada",
                    extra={
                        "titulo_candidato": titulo_candidato,
                        "titulo_existente": titulo,
                        "similaridade": float(similaridade),
                        "limiar": limiar_efetivo,
                    }
                )
                return True

        logger.info(
            "checar_duplicidade_semantica.sem_duplicata",
            extra={
                "titulo": titulo_candidato,
                "nicho": nicho,
                "total_comparados": len(similares),
                "limiar": limiar_efetivo,
            }
        )
        return False

    except Exception as e:
        logger.error(
            "checar_duplicidade_semantica.erro",
            extra={
                "titulo": titulo_candidato,
                "nicho": nicho,
                "erro": str(e),
            }
        )
        # Em caso de erro, não bloqueia a ideação (retorna False)
        # Mas o erro é logado para investigação
        return False
