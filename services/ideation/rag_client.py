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

logger = logging.getLogger("services.ideation.rag_client")


async def buscar_titulos_recentes(nicho: str, limite: int = 30) -> list[str]:
    """
    TODO (Fase 1): consultar a tabela `dados.videos_ideias` (ver db/models.py)
    e retornar os `titulo_sugerido` mais recentes para o nicho, ordenados por
    `data_criacao DESC`. Equivalente direto ao nó "Execute a SQL query" do
    fluxo n8n original.
    """
    logger.warning("buscar_titulos_recentes: stub — implementar consulta real ao Postgres")
    return []


async def checar_duplicidade_semantica(titulo_candidato: str, nicho: str) -> bool:
    """
    TODO (Fase 1, opcional/pode ficar para Fase 2): gerar embedding do
    título candidato e comparar via similaridade de cosseno com embeddings
    já armazenados (pgvector) para o nicho. Retorna True se for considerado
    duplicata (similaridade acima de um limiar, ex: 0.90).

    Para a primeira versão da Fase 1, é aceitável implementar apenas a
    checagem textual simples (via buscar_titulos_recentes) e deixar a
    checagem semântica com pgvector como próxima iteração.
    """
    logger.warning("checar_duplicidade_semantica: stub — não implementado na base inicial")
    return False
