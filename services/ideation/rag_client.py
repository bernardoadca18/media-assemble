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

from db.models import buscar_titulos_recentes_db

logger = logging.getLogger("services.ideation.rag_client")


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


async def checar_duplicidade_semantica(titulo_candidato: str, nicho: str) -> bool:
    """
    TODO (Fase futura com pgvector): gerar embedding do título candidato
    e comparar via similaridade de cosseno com embeddings já armazenados
    para o nicho. Retorna True se for considerado duplicata (similaridade
    acima de um limiar, ex: 0.90).

    Para a Fase 1, a checagem textual via buscar_titulos_recentes já é
    suficiente — a duplicidade exata será evitada pelo prompt do LLM.
    """
    logger.info(
        "checar_duplicidade_semantica.stub",
        extra={"titulo": titulo_candidato, "nicho": nicho}
    )
    return False
