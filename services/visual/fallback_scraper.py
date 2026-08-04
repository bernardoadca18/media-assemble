"""
FASE 4 — Fallback de assets via fontes externas (Pexels).

Acionado quando o banco local não possui asset compatível com as keywords da cena.
Baixa o asset para cache local em `data/assets_local/_fallback_cache/`.

Quanto a yt-dlp: está declarado como dependência, mas deve ser tratado como
último recurso devido a questões de licenciamento. Se implementado no futuro,
deixar claramente isolado e documentado.
"""
import hashlib
import logging
from pathlib import Path
from typing import NamedTuple

import httpx

from pipeline.config import settings

logger = logging.getLogger("services.visual.fallback_scraper")

# Diretório de cache para assets baixados
CACHE_DIR = Path("data/assets_local/_fallback_cache")

# Extensões suportadas por tipo
EXTENSOES_POR_TIPO = {
    "imagem": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "video": [".mp4", ".webm", ".mov"],
}


class AssetExterno(NamedTuple):
    """Resultado da busca externa de asset."""
    path: Path
    origem: str


async def _buscar_pexels(query: str, tipo_asset: str) -> AssetExterno | None:
    """
    Busca asset na API do Pexels.

    Args:
        query: Termo de busca
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    api_key = settings.pexels_api_key
    if not api_key:
        logger.warning("fallback_scraper.pexels_sem_api_key")
        return None

    # Determina endpoint baseado no tipo
    if tipo_asset == "video":
        endpoint = "https://api.pexels.com/videos/search"
    else:
        endpoint = "https://api.pexels.com/v1/search"

    headers = {"Authorization": api_key}
    params = {
        "query": query,
        "per_page": 5,  # Busca os 5 primeiros
        "page": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(endpoint, headers=headers, params=params)
            response.raise_for_status()
            data = response.json()
    except httpx.HTTPStatusError as e:
        logger.error(
            "fallback_scraper.pexels_erro_http",
            extra={"status": e.response.status_code, "query": query},
        )
        return None
    except httpx.RequestError as e:
        logger.error(
            "fallback_scraper.pexels_erro_conexao",
            extra={"erro": str(e), "query": query},
        )
        return None
    except Exception as e:
        logger.error(
            "fallback_scraper.pexels_erro_inesperado",
            extra={"erro": str(e), "query": query},
        )
        return None

    # Processa resposta baseado no tipo
    if tipo_asset == "video":
        return await _processar_resposta_video_pexels(data, query)
    else:
        return await _processar_resposta_imagem_pexels(data, query)


async def _processar_resposta_imagem_pexels(data: dict, query: str) -> AssetExterno | None:
    """
    Processa resposta da API de imagens do Pexels e baixa a primeira imagem.
    """
    photos = data.get("photos", [])
    if not photos:
        logger.info(
            "fallback_scraper.pexels_sem_imagens",
            extra={"query": query},
        )
        return None

    # Pega a primeira imagem
    photo = photos[0]
    photo_id = photo.get("id")
    src = photo.get("src", {})

    # Preferência por "large" (boa qualidade), fallback para "original"
    url = src.get("large") or src.get("original")
    if not url:
        logger.warning(
            "fallback_scraper.pexels_sem_url_imagem",
            extra={"photo_id": photo_id},
        )
        return None

    # Baixa o asset
    return await _baixar_asset(url, f"pexels_img_{photo_id}", "imagem")


async def _processar_resposta_video_pexels(data: dict, query: str) -> AssetExterno | None:
    """
    Processa resposta da API de vídeos do Pexels e baixa o primeiro vídeo.
    """
    videos = data.get("videos", [])
    if not videos:
        logger.info(
            "fallback_scraper.pexels_sem_videos",
            extra={"query": query},
        )
        return None

    # Pega o primeiro vídeo
    video = videos[0]
    video_id = video.get("id")
    video_files = video.get("video_files", [])

    if not video_files:
        logger.warning(
            "fallback_scraper.pexels_sem_arquivos_video",
            extra={"video_id": video_id},
        )
        return None

    # Preferência por MP4 de qualidade média (HD)
    video_file = None
    for vf in video_files:
        if vf.get("file_type") == "video/mp4":
            video_file = vf
            break

    if not video_file:
        video_file = video_files[0]

    url = video_file.get("link")
    if not url:
        logger.warning(
            "fallback_scraper.pexels_sem_url_video",
            extra={"video_id": video_id},
        )
        return None

    # Baixa o asset
    return await _baixar_asset(url, f"pexels_vid_{video_id}", "video")


async def _baixar_asset(url: str, nome_base: str, tipo_asset: str) -> AssetExterno | None:
    """
    Baixa asset da URL e salva no cache local.

    Args:
        url: URL do asset
        nome_base: Nome base para o arquivo (sem extensão)
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se sucesso, None caso contrário
    """
    # Garante diretório de cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url)
            response.raise_for_status()

            # Determina extensão baseada no Content-Type ou URL
            content_type = response.headers.get("content-type", "")
            extensao = _extrair_extensao(content_type, url, tipo_asset)

            # Gera nome único baseado em hash do conteúdo
            conteudo = response.content
            hash_conteudo = hashlib.md5(conteudo).hexdigest()[:12]
            nome_arquivo = f"{nome_base}_{hash_conteudo}{extensao}"
            caminho = CACHE_DIR / nome_arquivo

            # Salva arquivo
            caminho.write_bytes(conteudo)

            logger.info(
                "fallback_scraper.asset_baixado",
                extra={
                    "url": url,
                    "caminho": str(caminho),
                    "tamanho_bytes": len(conteudo),
                },
            )

            return AssetExterno(path=caminho, origem="fallback_pexels")

    except httpx.HTTPStatusError as e:
        logger.error(
            "fallback_scraper.download_erro_http",
            extra={"status": e.response.status_code, "url": url},
        )
        return None
    except httpx.RequestError as e:
        logger.error(
            "fallback_scraper.download_erro_conexao",
            extra={"erro": str(e), "url": url},
        )
        return None
    except Exception as e:
        logger.error(
            "fallback_scraper.download_erro_inesperado",
            extra={"erro": str(e), "url": url},
        )
        return None


def _extrair_extensao(content_type: str, url: str, tipo_asset: str) -> str:
    """
    Extrai extensão do arquivo baseada em Content-Type ou URL.
    """
    # Tenta extrair do Content-Type
    if "image/jpeg" in content_type or "image/jpg" in content_type:
        return ".jpg"
    if "image/png" in content_type:
        return ".png"
    if "image/gif" in content_type:
        return ".gif"
    if "image/webp" in content_type:
        return ".webp"
    if "video/mp4" in content_type:
        return ".mp4"
    if "video/webm" in content_type:
        return ".webm"

    # Tenta extrair da URL
    url_lower = url.lower()
    for ext in EXTENSOES_POR_TIPO.get(tipo_asset, []):
        if url_lower.endswith(ext):
            return ext

    # Fallback baseado no tipo
    if tipo_asset == "video":
        return ".mp4"
    return ".jpg"


async def buscar_asset_externo(
    keywords: list[str],
    fallback_query: str,
    tipo_asset: str,
) -> AssetExterno | None:
    """
    Busca asset em fontes externas quando o banco local não tem.

    Fontes (em ordem de preferência):
    1. Pexels API (imagens e vídeos gratuitos, licença permissiva)
    2. yt-dlp (último recurso, questões de licenciamento - NÃO IMPLEMENTADO)

    Args:
        keywords: Lista de keywords da cena (para logging)
        fallback_query: Query de fallback para busca externa
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    # Prioriza fallback_query, mas tenta keywords se vazio
    query = fallback_query or " ".join(keywords)

    if not query:
        logger.warning(
            "fallback_scraper.query_vazia",
            extra={"keywords": keywords},
        )
        return None

    logger.info(
        "fallback_scraper.buscar_pexels",
        extra={"query": query, "tipo_asset": tipo_asset},
    )

    # Busca no Pexels
    resultado = await _buscar_pexels(query, tipo_asset)

    if resultado:
        return resultado

    # yt-dlp seria implementado aqui como último recurso
    # Por ora, apenas loga que não há mais opções
    logger.warning(
        "fallback_scraper.sem_fontes_disponiveis",
        extra={"query": query, "tipo_asset": tipo_asset},
    )

    return None
