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
import os
from concurrent.futures import ThreadPoolExecutor

import feedparser
from pytrends.request import TrendReq

logger = logging.getLogger("services.trends.scraper")

# Executor para rodar operações síncronas do pytrends
_executor = ThreadPoolExecutor(max_workers=1)

def _obter_categoria_google_trends(nicho: str) -> int:
    """
    Obtém a categoria do Google Trends para o nicho.

    Args:
        nicho: Nome do nicho

    Returns:
        ID da categoria do Google Trends
    """
    try:
        from pipeline.nichos import obter_config_nicho
        config = obter_config_nicho(nicho)
        return config.categoria_google_trends
    except ValueError:
        # Fallback para categoria padrão (Entertainment)
        logger.warning(
            "scraper.nicho_nao_configurado",
            extra={"nicho": nicho, "fallback_categoria": 22}
        )
        return 22


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
        categoria = _obter_categoria_google_trends(nicho)

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


async def _coletar_reddit_rss(nicho: str, limite_por_subreddit: int = 5) -> list[str]:
    """
    Coleta posts em alta de subreddits via RSS público.

    Usa feeds RSS públicos do Reddit, sem necessidade de autenticação.
    Busca posts de /hot de cada subreddit configurado para o nicho.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite_por_subreddit: Máximo de posts por subreddit

    Returns:
        Lista de títulos de posts em alta
    """
    try:
        from pipeline.nichos import obter_config_nicho
        config = obter_config_nicho(nicho)
        subreddits = config.subreddits_sugeridos
    except ValueError:
        logger.warning("reddit_rss.nicho_nao_configurado", extra={"nicho": nicho})
        return []

    tendencias = []

    for subreddit in subreddits:
        try:
            # Feed RSS de posts "hot" do subreddit
            url = f"https://www.reddit.com/r/{subreddit}/hot/.rss"

            # feedparser é síncrono mas leve, executado diretamente
            feed = feedparser.parse(url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(
                    "reddit_rss.feed_erro",
                    extra={"subreddit": subreddit, "erro": str(feed.bozo_exception)}
                )
                continue

            for i, entry in enumerate(feed.entries[:limite_por_subreddit]):
                if hasattr(entry, "title"):
                    tendencias.append(entry.title)

            logger.info(
                "reddit_rss.posts_coletados",
                extra={"subreddit": subreddit, "total": min(len(feed.entries), limite_por_subreddit)}
            )

        except Exception as e:
            logger.error(
                "reddit_rss.erro_subreddit",
                extra={"subreddit": subreddit, "erro": str(e)}
            )
            continue

    logger.info(
        "reddit_rss.coleta_concluida",
        extra={"nicho": nicho, "total_posts": len(tendencias)}
    )

    return tendencias


async def _coletar_youtube_trending(nicho: str, limite: int = 10) -> list[str]:
    """
    Coleta vídeos em tendência via YouTube Data API v3.

    Usa categoria de vídeo específica por nicho para buscar trending videos.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite: Máximo de vídeos a retornar

    Returns:
        Lista de títulos de vídeos em tendência

    Requires:
        YOUTUBE_API_KEY configurada no ambiente
    """
    api_key = os.getenv("YOUTUBE_API_KEY")

    if not api_key:
        logger.warning("youtube_trending.sem_api_key", extra={"nicho": nicho})
        return []

    try:
        from googleapiclient.discovery import build
        from googleapiclient.errors import HttpError
        from pipeline.nichos import obter_config_nicho

        config = obter_config_nicho(nicho)
        categoria_id = config.categoria_google_trends

        # Criar cliente da API (síncrono)
        youtube = build("youtube", "v3", developerKey=api_key, static_discovery=False)

        # Buscar vídeos em tendência para a categoria
        # Executar chamada síncrona em thread separada
        def fetch_trending():
            request = youtube.videos().list(
                part="snippet",
                chart="mostPopular",
                regionCode="BR",
                videoCategoryId=categoria_id,
                maxResults=limite
            )
            return request.execute()

        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, fetch_trending)

        titulos = [item["snippet"]["title"] for item in response.get("items", [])]

        logger.info(
            "youtube_trending.videos_coletados",
            extra={"nicho": nicho, "categoria_id": categoria_id, "total": len(titulos)}
        )

        return titulos

    except HttpError as e:
        logger.error(
            "youtube_trending.erro_api",
            extra={"nicho": nicho, "status": e.resp.status, "erro": str(e)}
        )
        return []

    except Exception as e:
        logger.error(
            "youtube_trending.erro_inesperado",
            extra={"nicho": nicho, "erro": str(e)}
        )
        return []


async def coletar_tendencias(nicho: str) -> list[str]:
    """
    Retorna uma lista de tópicos/tendências brutos (texto livre) relevantes
    para o nicho informado.

    Combina múltiplas fontes (Google Trends, Reddit, YouTube trending, RSS de nicho,
    Google Custom Search) e retorna uma lista consolidada. Fontes não implementadas
    ou com falha retornam lista vazia e não quebram o pipeline.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)

    Returns:
        Lista de strings com tendências brutas (texto livre)
    """
    logger.info("coletar_tendencias.iniciando", extra={"nicho": nicho})

    # Coleta de todas as fontes em paralelo
    from services.trends.rss_sources import coletar_rss_nicho, coletar_custom_search

    google_trends_task = _coletar_google_trends(nicho)
    reddit_task = _coletar_reddit_rss(nicho)
    youtube_task = _coletar_youtube_trending(nicho)
    rss_nicho_task = coletar_rss_nicho(nicho)
    custom_search_task = coletar_custom_search(nicho)

    resultados = await asyncio.gather(
        google_trends_task,
        reddit_task,
        youtube_task,
        rss_nicho_task,
        custom_search_task,
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
