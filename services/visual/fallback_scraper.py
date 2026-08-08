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
import os
from pathlib import Path
from typing import NamedTuple

import httpx

from pipeline.config import settings
from utils.retry import ErroPermanente, ErroTransitorio, com_retry

logger = logging.getLogger("services.visual.fallback_scraper")

# Diretório de cache para assets baixados
CACHE_DIR = Path("data/assets_local/_fallback_cache")

# Extensões suportadas por tipo
EXTENSOES_POR_TIPO = {
    "imagem": [".jpg", ".jpeg", ".png", ".gif", ".webp"],
    "video": [".mp4", ".webm", ".mov"],
}


class AssetExterno(NamedTuple):
    """
    Resultado da busca externa de asset.

    Campos de licenciamento:
    - atribuicao_requerida: Se True, o asset exige atribuição obrigatória
    - texto_atribuicao: Texto formatado para atribuição (ex: "Photo by John Doe on Unsplash")
    - licenca: Código da licença (ex: "CC BY 4.0", "Pixabay License", "Pexels License")
    - fotografo: Nome do fotógrafo/criador (para atribuição)
    - url_perfil: URL do perfil do criador (para link de atribuição)
    """
    path: Path
    origem: str  # "fallback_pexels", "fallback_pixabay", "fallback_unsplash", "fallback_wikimedia"
    atribuicao_requerida: bool = False
    texto_atribuicao: str | None = None
    licenca: str | None = None
    fotografo: str | None = None
    url_perfil: str | None = None


async def _buscar_pexels_interno(query: str, tipo_asset: str) -> dict:
    """Implementação interna da busca no Pexels sem retry."""
    api_key = settings.pexels_api_key
    if not api_key:
        raise ErroPermanente("API key do Pexels não configurada")

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

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()


async def _buscar_pexels(query: str, tipo_asset: str) -> AssetExterno | None:
    """
    Busca asset na API do Pexels com retry.

    Args:
        query: Termo de busca
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    async def _chamada():
        try:
            return await _buscar_pexels_interno(query, tipo_asset)
        except httpx.HTTPStatusError as e:
            # Rate limit (429) e erros de servidor (5xx) são transitórios
            if e.response.status_code in (429, 502, 503, 504):
                logger.warning(
                    "fallback_scraper.pexels_erro_transitorio_http",
                    extra={"status": e.response.status_code, "query": query},
                )
                raise ErroTransitorio(str(e)) from e
            # Erros de cliente (4xx exceto 429) são permanentes
            logger.error(
                "fallback_scraper.pexels_erro_permanente_http",
                extra={"status": e.response.status_code, "query": query},
            )
            raise ErroPermanente(str(e)) from e
        except httpx.RequestError as e:
            # Erros de conexão/timeout são transitórios
            logger.warning(
                "fallback_scraper.pexels_erro_transitorio_conexao",
                extra={"erro": str(e), "query": query},
            )
            raise ErroTransitorio(str(e)) from e
        except ErroPermanente:
            raise
        except Exception as e:
            logger.error(
                "fallback_scraper.pexels_erro_inesperado",
                extra={"erro": str(e), "query": query},
            )
            raise ErroPermanente(str(e)) from e

    try:
        data = await com_retry(_chamada, nome_operacao="pexels.busca", max_tentativas=3)
    except (ErroPermanente, Exception):
        # Falha após retry ou erro permanente
        return None

    # Processa resposta baseado no tipo
    if tipo_asset == "video":
        return await _processar_resposta_video_pexels(data, query)
    else:
        return await _processar_resposta_imagem_pexels(data, query)


# =============================================================================
# Fase 8.9.2 — Novas fontes de fallback (Pixabay, Unsplash, Wikimedia Commons)
# =============================================================================


async def _buscar_pixabay(query: str, tipo_asset: str) -> AssetExterno | None:
    """
    Busca asset na API do Pixabay com retry.

    Pixabay: uso comercial gratuito, sem exigência de atribuição.

    Args:
        query: Termos de busca
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    api_key = os.getenv("PIXABAY_API_KEY")
    if not api_key:
        logger.info("pixabay.sem_api_key")
        return None

    async def _chamada():
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Pixabay usa mesmo endpoint para imagens e vídeos
            url = "https://pixabay.com/api/"
            params = {
                "key": api_key,
                "q": query,
                "per_page": 10,
                "lang": "pt",
                "safesearch": "true",
            }

            if tipo_asset == "video":
                url = "https://pixabay.com/api/videos/"

            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    try:
        data = await com_retry(_chamada, nome_operacao="pixabay.busca", max_tentativas=3)
    except (ErroPermanente, Exception):
        return None

    # Processa resposta
    if tipo_asset == "video":
        return await _processar_resposta_video_pixabay(data, query)
    else:
        return await _processar_resposta_imagem_pixabay(data, query)


async def _processar_resposta_imagem_pixabay(data: dict, query: str) -> AssetExterno | None:
    """Processa resposta da API de imagens do Pixabay."""
    hits = data.get("hits", [])
    if not hits:
        logger.info("pixabay.sem_imagens", extra={"query": query})
        return None

    # Pega a primeira imagem (ordem por relevância)
    hit = hits[0]
    image_url = hit.get("largeImageURL") or hit.get("webformatURL")
    if not image_url:
        return None

    # Pixabay não exige atribuição, mas guardamos o nome do fotografo
    fotografo = hit.get("user")
    foto_id = hit.get("id")

    logger.info(
        "pixabay.imagem_encontrada",
        extra={"foto_id": foto_id, "fotografo": fotografo, "query": query},
    )

    return await _baixar_asset_interno(
        url=image_url,
        nome_base=f"pixabay_{foto_id}",
        tipo_asset="imagem",
        origem="fallback_pixabay",
        atribuicao_requerida=False,  # Pixabay não exige atribuição
        texto_atribuicao=None,
        licenca="Pixabay License",
        fotografo=fotografo,
        url_perfil=f"https://pixabay.com/users/{fotografo}-{hit.get('user_id', '')}/" if fotografo else None,
    )


async def _processar_resposta_video_pixabay(data: dict, query: str) -> AssetExterno | None:
    """Processa resposta da API de vídeos do Pixabay."""
    hits = data.get("hits", [])
    if not hits:
        logger.info("pixabay.sem_videos", extra={"query": query})
        return None

    hit = hits[0]
    videos = hit.get("videos", {})
    # Prefere qualidade média (larger ainda é baixável)
    video_info = videos.get("medium") or videos.get("large") or videos.get("small")
    if not video_info:
        return None

    video_url = video_info.get("url")
    if not video_url:
        return None

    fotografo = hit.get("user")
    video_id = hit.get("id")

    logger.info(
        "pixabay.video_encontrado",
        extra={"video_id": video_id, "fotografo": fotografo, "query": query},
    )

    return await _baixar_asset_interno(
        url=video_url,
        nome_base=f"pixabay_{video_id}",
        tipo_asset="video",
        origem="fallback_pixabay",
        atribuicao_requerida=False,
        texto_atribuicao=None,
        licenca="Pixabay License",
        fotografo=fotografo,
        url_perfil=f"https://pixabay.com/users/{fotografo}-{hit.get('user_id', '')}/" if fotografo else None,
    )


async def _buscar_unsplash(query: str, tipo_asset: str) -> AssetExterno | None:
    """
    Busca asset na API do Unsplash com retry.

    Unsplash: uso comercial gratuito via API, mas ATRIBUIÇÃO É OBRIGATÓRIA.
    Quando a imagem for usada num vídeo publicado, a atribuição
    (foto + fotógrafo, com link ao perfil) deve ser incluída na descrição.

    Args:
        query: Termos de busca
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    api_key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not api_key:
        logger.info("unsplash.sem_api_key")
        return None

    async def _chamada():
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = "https://api.unsplash.com/search/photos"
            params = {
                "query": query,
                "per_page": 10,
                "orientation": "landscape",  # Melhor para vídeos
            }

            response = await client.get(
                url,
                params=params,
                headers={"Authorization": f"Client-ID {api_key}"}
            )
            response.raise_for_status()
            return response.json()

    try:
        data = await com_retry(_chamada, nome_operacao="unsplash.busca", max_tentativas=3)
    except (ErroPermanente, Exception):
        return None

    return await _processar_resposta_unsplash(data, query)


async def _processar_resposta_unsplash(data: dict, query: str) -> AssetExterno | None:
    """
    Processa resposta da API do Unsplash e baixa a primeira imagem.

    IMPORTANTE: Unsplash via API exige atribuição obrigatória.
    """
    results = data.get("results", [])
    if not results:
        logger.info("unsplash.sem_imagens", extra={"query": query})
        return None

    photo = results[0]
    photo_id = photo.get("id")

    # URLs da imagem
    urls = photo.get("urls", {})
    image_url = urls.get("regular") or urls.get("full") or urls.get("raw")
    if not image_url:
        return None

    # Informações do fotografo para atribuição
    user = photo.get("user", {})
    fotografo = user.get("name")
    username = user.get("username")
    user_url = f"https://unsplash.com/@{username}" if username else None

    # Texto de atribuição obrigatório
    texto_atribuicao = f"Photo by {fotografo} on Unsplash"
    if user_url:
        texto_atribuicao = f"Photo by {fotografo} on Unsplash ({user_url})"

    logger.info(
        "unsplash.imagem_encontrada",
        extra={"photo_id": photo_id, "fotografo": fotografo, "query": query},
    )

    return await _baixar_asset_interno(
        url=image_url,
        nome_base=f"unsplash_{photo_id}",
        tipo_asset="imagem",
        origem="fallback_unsplash",
        atribuicao_requerida=True,  # OBRIGATÓRIO
        texto_atribuicao=texto_atribuicao,
        licenca="Unsplash License",
        fotografo=fotografo,
        url_perfil=user_url,
    )


async def _buscar_wikimedia(query: str, tipo_asset: str) -> AssetExterno | None:
    """
    Busca asset na API do Wikimedia Commons com retry.

    Wikimedia Commons: cada arquivo tem sua própria licença (domínio público,
    CC BY, CC BY-SA, etc.). A licença específica deve ser lida da resposta
    da API e persistida junto ao asset.

    Args:
        query: Termos de busca
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se encontrar, None caso contrário
    """
    async def _chamada():
        async with httpx.AsyncClient(timeout=30.0) as client:
            # API do Wikimedia Commons
            url = "https://commons.wikimedia.org/w/api.php"
            params = {
                "action": "query",
                "generator": "search",
                "gsrnamespace": "6",  # File namespace
                "gsrsearch": f"{query} filetype:bitmap",
                "gsrlimit": 10,
                "prop": "imageinfo",
                "iiprop": "url|extmetadata",
                "format": "json",
            }

            response = await client.get(url, params=params)
            response.raise_for_status()
            return response.json()

    try:
        data = await com_retry(_chamada, nome_operacao="wikimedia.busca", max_tentativas=3)
    except (ErroPermanente, Exception):
        return None

    return await _processar_resposta_wikimedia(data, query)


async def _processar_resposta_wikimedia(data: dict, query: str) -> AssetExterno | None:
    """
    Processa resposta da API do Wikimedia Commons e baixa a primeira imagem.

    IMPORTANTE: Lê a licença específica de cada arquivo da resposta da API.
    """
    query_data = data.get("query", {})
    pages = query_data.get("pages", {})

    if not pages:
        logger.info("wikimedia.sem_imagens", extra={"query": query})
        return None

    # Pega a primeira página (ordem por relevância)
    page = next(iter(pages.values()), None)
    if not page:
        return None

    title = page.get("title", "")
    imageinfo = page.get("imageinfo", [])
    if not imageinfo:
        return None

    info = imageinfo[0]
    image_url = info.get("url")
    if not image_url:
        return None

    # Extrair licença do extmetadata
    metadata = info.get("extmetadata", {})
    license_info = metadata.get("LicenseShortName", {})
    licenca = license_info.get("value", "Unknown")

    # Verificar se atribuição é requerida
    attribution_required = metadata.get("AttributionRequired", {})
    atribuicao_requerida = attribution_required.get("value", "false").lower() == "true"

    # Artista/fotografo
    artist_info = metadata.get("Artist", {})
    artista = artist_info.get("value", "Unknown")

    # Limpar HTML do nome do artista
    import re
    artista = re.sub(r'<[^>]+>', '', artista) if artista else "Unknown"

    logger.info(
        "wikimedia.imagem_encontrada",
        extra={"title": title, "licenca": licenca, "query": query},
    )

    # Texto de atribuição se necessário
    texto_atribuicao = None
    if atribuicao_requerida:
        texto_atribuicao = f"{artista} - Wikimedia Commons ({licenca})"

    return await _baixar_asset_interno(
        url=image_url,
        nome_base=f"wikimedia_{page.get('pageid', 'unknown')}",
        tipo_asset="imagem",
        origem="fallback_wikimedia",
        atribuicao_requerida=atribuicao_requerida,
        texto_atribuicao=texto_atribuicao,
        licenca=licenca,
        fotografo=artista,
        url_perfil=f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}" if title else None,
    )


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


async def _baixar_asset_interno(
    url: str,
    nome_base: str,
    tipo_asset: str,
    origem: str = "fallback_pexels",
    atribuicao_requerida: bool = False,
    texto_atribuicao: str | None = None,
    licenca: str | None = None,
    fotografo: str | None = None,
    url_perfil: str | None = None,
) -> AssetExterno:
    """Implementação interna do download sem retry."""
    # Garante diretório de cache
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

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
                "origem": origem,
            },
        )

        return AssetExterno(
            path=caminho,
            origem=origem,
            atribuicao_requerida=atribuicao_requerida,
            texto_atribuicao=texto_atribuicao,
            licenca=licenca,
            fotografo=fotografo,
            url_perfil=url_perfil,
        )


async def _baixar_asset(url: str, nome_base: str, tipo_asset: str) -> AssetExterno | None:
    """
    Baixa asset da URL e salva no cache local com retry.

    Args:
        url: URL do asset
        nome_base: Nome base para o arquivo (sem extensão)
        tipo_asset: "imagem" ou "video"

    Returns:
        AssetExterno se sucesso, None caso contrário
    """
    async def _chamada():
        try:
            return await _baixar_asset_interno(url, nome_base, tipo_asset)
        except httpx.HTTPStatusError as e:
            # Rate limit (429) e erros de servidor (5xx) são transitórios
            if e.response.status_code in (429, 502, 503, 504):
                logger.warning(
                    "fallback_scraper.download_erro_transitorio_http",
                    extra={"status": e.response.status_code, "url": url},
                )
                raise ErroTransitorio(str(e)) from e
            # Erros de cliente (4xx exceto 429) são permanentes
            logger.error(
                "fallback_scraper.download_erro_permanente_http",
                extra={"status": e.response.status_code, "url": url},
            )
            raise ErroPermanente(str(e)) from e
        except httpx.RequestError as e:
            # Erros de conexão/timeout são transitórios
            logger.warning(
                "fallback_scraper.download_erro_transitorio_conexao",
                extra={"erro": str(e), "url": url},
            )
            raise ErroTransitorio(str(e)) from e
        except ErroPermanente:
            raise
        except Exception as e:
            logger.error(
                "fallback_scraper.download_erro_inesperado",
                extra={"erro": str(e), "url": url},
            )
            raise ErroPermanente(str(e)) from e

    try:
        return await com_retry(_chamada, nome_operacao="pexels.download", max_tentativas=3)
    except (ErroPermanente, Exception):
        # Falha após retry ou erro permanente
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
    contexto_cena: str | None = None,
    usar_triagem_llm: bool = True,
) -> AssetExterno | None:
    """
    Busca asset em fontes externas quando o banco local não tem.

    Cascata de fallback (ordem de preferência):
    1. Pexels API (imagens e vídeos gratuitos, licença permissiva)
    2. Pixabay (uso comercial gratuito, sem atribuição)
    3. Unsplash (uso comercial gratuito, atribuição OBRIGATÓRIA via API)
    4. Wikimedia Commons (licenças variadas, lidas por arquivo)

    Cada fonte pode ter triagem por LLM antes de aceitar o asset.

    Args:
        keywords: Lista de keywords da cena (para logging)
        fallback_query: Query de fallback para busca externa
        tipo_asset: "imagem" ou "video"
        contexto_cena: Contexto da cena para triagem por LLM (opcional)
        usar_triagem_llm: Se True, usa LLM para validar relevância do asset

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
        "fallback_scraper.iniciando_busca",
        extra={"query": query, "tipo_asset": tipo_asset, "triagem_llm": usar_triagem_llm},
    )

    # Lista de fontes em ordem de preferência
    fontes = [
        ("pexels", _buscar_pexels),
        ("pixabay", _buscar_pixabay),
        ("unsplash", _buscar_unsplash),
        ("wikimedia", _buscar_wikimedia),
    ]

    for nome_fonte, funcao_busca in fontes:
        logger.info(
            f"fallback_scraper.tentando_fonte",
            extra={"fonte": nome_fonte, "query": query},
        )

        resultado = await funcao_busca(query, tipo_asset)

        if not resultado:
            continue

        # Triagem por LLM se habilitada
        if usar_triagem_llm and contexto_cena:
            from services.visual.triagem_llm import triar_asset_llm

            # Monta descrição do asset para triagem
            descricao = f"Origem: {resultado.origem}"
            if resultado.fotografo:
                descricao += f", Fotógrafo: {resultado.fotografo}"
            if resultado.licenca:
                descricao += f", Licença: {resultado.licenca}"

            aprovado = await triar_asset_llm(
                descricao_asset=descricao,
                contexto_cena=contexto_cena,
                keywords=keywords,
                tipo_asset=tipo_asset,
            )

            if not aprovado:
                logger.info(
                    "fallback_scraper.asset_rejeitado_llm",
                    extra={"fonte": nome_fonte, "query": query},
                )
                # Remove asset rejeitado
                try:
                    resultado.path.unlink(missing_ok=True)
                except Exception:
                    pass
                continue

        # Asset aprovado (com ou sem triagem LLM)
        logger.info(
            "fallback_scraper.asset_aceito",
            extra={
                "fonte": nome_fonte,
                "query": query,
                "atribuicao_requerida": resultado.atribuicao_requerida,
                "licenca": resultado.licenca,
            },
        )

        return resultado

    logger.warning(
        "fallback_scraper.sem_fontes_disponiveis",
        extra={"query": query, "tipo_asset": tipo_asset},
    )

    return None
