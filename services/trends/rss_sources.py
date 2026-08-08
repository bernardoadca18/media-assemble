"""
Fase 8.9.1 — Fontes de tendência via RSS e Custom Search.

Este módulo estende as fontes de tendências com:
- Feeds RSS específicos por nicho (TechCrunch, The Verge, etc.)
- Google Custom Search API (opcional, gratuito até 100 buscas/dia)

Ambas as fontes são gratuitas e falham de forma isolada sem quebrar o pipeline.
"""
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import feedparser

logger = logging.getLogger("services.trends.rss_sources")


# =============================================================================
# Feeds RSS por nicho
# =============================================================================

# Feeds RSS públicos de sites de notícia/nicho
# Nota: URLs podem mudar ao longo do tempo — verificar disponibilidade na implementação
FEEDS_RSS_POR_NICHO: dict[str, list[str]] = {
    "cultura_pop": [
        # Entertainment/Pop Culture
        "https://feeds.feedburner.com/ign/games-all",  # IGN Games
        "https://www.reddit.com/r/entertainment/.rss",  # Reddit Entertainment
    ],
    "tecnologia": [
        # Technology news
        "https://techcrunch.com/feed/",  # TechCrunch
        "https://www.theverge.com/rss/index.xml",  # The Verge
        "https://feeds.arstechnica.com/arstechnica/technology-lab",  # Ars Technica
    ],
    "futebol": [
        # Sports/Football (Brazilian focus)
        "https://www.reddit.com/r/soccer/.rss",  # Reddit Soccer
    ],
}


async def coletar_rss_nicho(nicho: str, limite_por_feed: int = 10) -> list[str]:
    """
    Coleta títulos de posts recentes de feeds RSS específicos do nicho.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite_por_feed: Máximo de posts por feed

    Returns:
        Lista de títulos de posts/publicações
    """
    feeds_urls = FEEDS_RSS_POR_NICHO.get(nicho, [])

    if not feeds_urls:
        logger.info(
            "rss_nicho.sem_feeds_configurados",
            extra={"nicho": nicho}
        )
        return []

    tendencias = []
    janela_tempo = datetime.now(timezone.utc) - timedelta(hours=48)  # Últimas 48h

    for feed_url in feeds_urls:
        try:
            # feedparser é síncrono mas leve, executado diretamente
            feed = feedparser.parse(feed_url)

            if feed.bozo and feed.bozo_exception:
                logger.warning(
                    "rss_nicho.feed_erro",
                    extra={"feed": feed_url, "erro": str(feed.bozo_exception)}
                )
                continue

            # Contador de posts dentro da janela de tempo
            posts_recentes = 0

            for entry in feed.entries[:limite_por_feed * 2]:  # Busca mais para filtrar por data
                if not hasattr(entry, "title"):
                    continue

                # Filtrar por data de publicação (se disponível)
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        data_pub = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
                        if data_pub < janela_tempo:
                            continue  # Muito antigo
                    except Exception:
                        pass  # Se não conseguir parsear, inclui mesmo assim

                tendencias.append(entry.title)
                posts_recentes += 1

                if posts_recentes >= limite_por_feed:
                    break

            logger.info(
                "rss_nicho.posts_coletados",
                extra={"feed": feed_url, "total": posts_recentes}
            )

        except Exception as e:
            logger.error(
                "rss_nicho.erro_feed",
                extra={"feed": feed_url, "erro": str(e)}
            )
            continue

    logger.info(
        "rss_nicho.coleta_concluida",
        extra={"nicho": nicho, "total_posts": len(tendencias)}
    )

    return tendencias


# =============================================================================
# Google Custom Search API
# =============================================================================

# Arquivo para persistir contador diário de uso
COTA_CSE_FILE = "/tmp/gameplay_pipeline_cse_quota.json"


def _carregar_cota_diaria() -> dict:
    """Carrega contador de uso diário do Custom Search do arquivo."""
    try:
        with open(COTA_CSE_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _salvar_cota_diaria(cota: dict) -> None:
    """Salva contador de uso diário do Custom Search no arquivo."""
    try:
        with open(COTA_CSE_FILE, "w") as f:
            json.dump(cota, f)
    except Exception as e:
        logger.warning(
            "cse.erro_salvar_cota",
            extra={"erro": str(e)}
        )


def _verificar_e_incrementar_cota_cse() -> bool:
    """
    Verifica se há cota disponível e incrementa o contador.

    Returns:
        True se há cota disponível, False se limite diário foi atingido
    """
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        logger.info("cse.nao_configurado")
        return False

    # Limite gratuito: 100 buscas/dia
    LIMITE_DIARIO = 100

    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cota = _carregar_cota_diaria()

    # Reset se dia mudou
    if cota.get("data") != hoje:
        cota = {"data": hoje, "contador": 0}

    # Verificar limite
    if cota.get("contador", 0) >= LIMITE_DIARIO:
        logger.warning(
            "cse.limite_diario_atingido",
            extra={"contador": cota["contador"], "limite": LIMITE_DIARIO}
        )
        return False

    # Incrementar e salvar
    cota["contador"] = cota.get("contador", 0) + 1
    _salvar_cota_diaria(cota)

    logger.info(
        "cse.cota_incrementada",
        extra={"contador": cota["contador"], "limite": LIMITE_DIARIO}
    )

    return True


async def coletar_custom_search(nicho: str, limite: int = 10) -> list[str]:
    """
    Coleta tendências via Google Custom Search API.

    Usa a API gratuita (100 buscas/dia) para buscar notícias/tendências
    relevantes para o nicho.

    Args:
        nicho: Nicho do canal (cultura_pop, tecnologia, futebol)
        limite: Número máximo de resultados

    Returns:
        Lista de títulos de páginas/resultados

    Requires:
        GOOGLE_CSE_API_KEY e GOOGLE_CSE_ID configurados no ambiente
    """
    api_key = os.getenv("GOOGLE_CSE_API_KEY")
    cse_id = os.getenv("GOOGLE_CSE_ID")

    if not api_key or not cse_id:
        logger.info("cse.nao_configurado", extra={"nicho": nicho})
        return []

    # Verificar cota diária
    if not _verificar_e_incrementar_cota_cse():
        return []

    try:
        import aiohttp

        # Query específica por nicho
        queries_por_nicho = {
            "cultura_pop": "trending entertainment news movies games",
            "tecnologia": "trending technology news AI programming",
            "futebol": "trending football news soccer brasileirão",
        }

        query = queries_por_nicho.get(nicho, f"trending {nicho} news")

        # Montar URL da API
        url = "https://www.googleapis.com/customsearch/v1"
        params = {
            "key": api_key,
            "cx": cse_id,
            "q": query,
            "num": limite,
            "dateRestrict": "d1",  # Últimas 24h
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                if response.status == 403:
                    logger.error(
                        "cse.quota_exceeded",
                        extra={"nicho": nicho, "status": response.status}
                    )
                    return []

                if response.status != 200:
                    logger.error(
                        "cse.erro_api",
                        extra={"nicho": nicho, "status": response.status}
                    )
                    return []

                data = await response.json()

        # Extrair títulos dos resultados
        titulos = []
        for item in data.get("items", []):
            if "title" in item:
                titulos.append(item["title"])

        logger.info(
            "cse.resultados_coletados",
            extra={"nicho": nicho, "total": len(titulos)}
        )

        return titulos

    except Exception as e:
        logger.error(
            "cse.erro_inesperado",
            extra={"nicho": nicho, "erro": str(e)}
        )
        return []
