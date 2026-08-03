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
Você recebe uma lista bruta de tendências extraídas de fontes como Google Trends,
redes sociais e buscadores. Sua tarefa é:

1. Limpar termos genéricos ou irrelevantes (ex: "Brasil", "2024", datas, nomes de pessoas não relacionadas a cultura pop)
2. Remover duplicatas ou termos muito similares
3. Filtrar apenas tópicos relacionados a cultura pop, entretenimento, filmes, séries, anime, jogos e lore
4. Retornar APENAS uma lista simples de tópicos, um por linha, sem numeração, sem comentários, sem markdown

Lista bruta:
{tendencias}

Tópicos relevantes (um por linha):
"""


async def normalizar_tendencias(tendencias_brutas: list[str]) -> list[str]:
    """
    Normaliza uma lista de tendências brutas usando LLM local.

    Args:
        tendencias_brutas: Lista de strings com tendências coletadas

    Returns:
        Lista limpa e filtrada de tópicos relevantes
    """
    if not tendencias_brutas:
        logger.info("normalizar_tendencias: lista de entrada vazia, retornando vazio")
        return []

    prompt = PROMPT_NORMALIZACAO.format(tendencias="\n".join(tendencias_brutas))

    try:
        resposta = await complete_local(prompt)

        # Processa a resposta: remove marcadores de lista, espaços extras
        linhas = []
        for linha in resposta.splitlines():
            linha = linha.strip()
            # Remove marcadores comuns de lista
            linha = linha.lstrip("-•>* ")
            if linha and len(linha) > 2:  # Ignora linhas muito curtas
                linhas.append(linha)

        logger.info(
            "normalizar_tendencias.concluido",
            extra={"entrada": len(tendencias_brutas), "saida": len(linhas)}
        )

        return linhas

    except Exception as e:
        logger.error(
            "normalizar_tendencias.erro",
            extra={"erro": str(e)}
        )
        # Em caso de erro, retorna a lista original (fallback)
        return tendencias_brutas
