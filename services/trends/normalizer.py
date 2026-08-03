"""
FASE 1 — Normalização de tendências via LLM leve.

Recebe a lista bruta de tendências (texto livre, possivelmente ruidoso) e
usa um modelo pequeno/local (via LiteLLM) para limpar, deduplicar e
estruturar em uma lista curta e objetiva de tópicos, no formato esperado
pelo agente de ideação.
"""
import logging

from utils.litellm_client import complete_local
from pipeline.config import settings

logger = logging.getLogger("services.trends.normalizer")

PROMPT_NORMALIZACAO = """\
Você recebe uma lista bruta de tendências extraídas de redes sociais e
buscadores. Limpe, remova duplicatas e itens irrelevantes (não relacionados
a cultura pop/games/filmes/séries/anime), e devolva APENAS uma lista simples
de tópicos, um por linha, sem numeração, sem comentários.

Lista bruta:
{tendencias}
"""


async def normalizar_tendencias(tendencias_brutas: list[str]) -> list[str]:
    if not tendencias_brutas:
        logger.info("normalizar_tendencias: lista de entrada vazia, retornando vazio")
        return []

    prompt = PROMPT_NORMALIZACAO.format(tendencias="\n".join(tendencias_brutas))
    resposta = await complete_local(prompt)

    linhas = [linha.strip("-• \t") for linha in resposta.splitlines() if linha.strip()]
    return linhas
