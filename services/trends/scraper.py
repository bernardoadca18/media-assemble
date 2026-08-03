"""
FASE 1 — Coleta de tendências.

Responsável por buscar tópicos em alta em fontes externas (X/Twitter, Google
Trends, Reddit, YouTube trending) para o nicho informado. Substitui a fonte
`{{ $node["Webhook"].json.body.raw_trends }}` que antes era enviada
manualmente/externamente para o fluxo n8n — aqui o próprio pipeline Python
passa a ser responsável por buscar esses dados.

Escopo da Fase 1:
- Implementar ao menos 1 fonte real (ex: Google Trends via `pytrends` ou
  scraping direto) de forma funcional.
- As demais fontes podem ficar como stubs anotados com TODO, retornando
  lista vazia, sem quebrar o pipeline.
- Sempre devolver uma lista de strings "cruas" (texto livre), que serão
  limpas/estruturadas pelo normalizer.py em seguida.
"""
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from pytrends.request import TrendReq

logger = logging.getLogger("services.trends.scraper")

# Executor para rodar operações síncronas do pytrends
_executor = ThreadPoolExecutor(max_workers=1)

# Mapeamento de nicho para categoria do Google Trends
# Categorias: https://github.com/pat310/google-trends-api/wiki/Google-Trends-Categories
NICHO_PARA_CATEGORIA_GOOGLE_TRENDS = {
    "cultura_pop": 22,  # Entertainment (Entretenimento)
    "tecnologia": 5,    # Technology (Tecnologia)
    "futebol": 20,      # Sports (Esportes)
}


def _coletar_google_trends_sync(nicho: str, limite: int = 20) -> list[str]:
    """
    Coleta tendências do Google Trends de forma síncrona.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite: Número máximo de tendências a retornar

    Returns:
        Lista de tópicos em alta
    """
    try:
        categoria = NICHO_PARA_CATEGORIA_GOOGLE_TRENDS.get(nicho, 22)

        pytrends = TrendReq(
            hl="pt-BR",
            tz=-180,  # Brasília timezone (UTC-3)
        )

        # Busca tendências diárias para a categoria
        pytrends.build_payload(
            kw_list=[],
            cat=categoria,
            timeframe="now 7-d",
            geo="BR",
        )

        # Tenta obter sugestões de busca
        sugestoes = pytrends.suggestions(keyword="")

        if sugestoes:
            tendencias = [s["title"] for s in sugestoes[:limite]]
            logger.info(
                "google_trends.sugestoes_coletadas",
                extra={"nicho": nicho, "total": len(tendencias)}
            )
            return tendencias

        # Fallback: busca tópicos em alta (trending searches)
        trending = pytrends.trending_searches(pn="brazil")
        if not trending.empty:
            tendencias = trending.iloc[:, 0].tolist()[:limite]
            logger.info(
                "google_trends.trending_coletadas",
                extra={"nicho": nicho, "total": len(tendencias)}
            )
            return tendencias

        logger.warning("google_trends.sem_resultados", extra={"nicho": nicho})
        return []

    except Exception as e:
        logger.error(
            "google_trends.erro",
            extra={"nicho": nicho, "erro": str(e)}
        )
        return []


async def _coletar_google_trends(nicho: str, limite: int = 20) -> list[str]:
    """
    Wrapper assíncrono para coleta do Google Trends.

    O pytrends é uma biblioteca síncrona que faz requisições HTTP bloqueantes.
    Usamos um ThreadPoolExecutor para não bloquear o event loop do asyncio.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        _executor,
        _coletar_google_trends_sync,
        nicho,
        limite
    )


async def _coletar_reddit_stub(nicho: str) -> list[str]:
    """
    TODO (Fase futura): Implementar coleta via API do Reddit.

    Subreddits sugeridos por nicho:
      - cultura_pop: r/anime, r/movies, r/gaming, r/television
      - tecnologia: r/technology, r/programming, r/gadgets
      - futebol: r/soccer, r/football

    Por ora, retorna lista vazia sem quebrar o pipeline.
    """
    logger.info("reddit.stub_nao_implementado", extra={"nicho": nicho})
    return []


async def _coletar_youtube_trending_stub(nicho: str) -> list[str]:
    """
    TODO (Fase futura): Implementar coleta de vídeos em alta do YouTube.

    Requer YouTube Data API v3 (chave de API necessária).

    Por ora, retorna lista vazia sem quebrar o pipeline.
    """
    logger.info("youtube_trending.stub_nao_implementado", extra={"nicho": nicho})
    return []


async def coletar_tendencias(nicho: str) -> list[str]:
    """
    Retorna uma lista de tópicos/tendências brutos (texto livre) relevantes
    para o nicho informado.

    Combina múltiplas fontes (Google Trends, Reddit, YouTube trending) e
    retorna uma lista consolidada. Fontes não implementadas retornam lista
    vazia e não quebram o pipeline.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)

    Returns:
        Lista de strings com tendências brutas (texto livre)
    """
    logger.info("coletar_tendencias.iniciando", extra={"nicho": nicho})

    # Coleta de todas as fontes em paralelo
    google_trends_task = _coletar_google_trends(nicho)
    reddit_task = _coletar_reddit_stub(nicho)
    youtube_task = _coletar_youtube_trending_stub(nicho)

    resultados = await asyncio.gather(
        google_trends_task,
        reddit_task,
        youtube_task,
        return_exceptions=True,
    )

    tendencias = []

    for resultado in resultados:
        if isinstance(resultado, Exception):
            logger.error("coletar_tendencias.fonte_falhou", extra={"erro": str(resultado)})
            continue
        if isinstance(resultado, list):
            tendencias.extend(resultado)

    # Remove duplicatas preservando ordem
    tendencias_unicas = list(dict.fromkeys(tendencias))

    logger.info(
        "coletar_tendencias.concluido",
        extra={"nicho": nicho, "total": len(tendencias_unicas)}
    )

    return tendencias_unicas
