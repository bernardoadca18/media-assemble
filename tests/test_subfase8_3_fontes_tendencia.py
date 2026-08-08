"""
Testes da Subfase 8.3 — Diversificação de fontes de tendência.

Cobertura:
- Coleta via Reddit RSS
- Coleta via YouTube Data API v3
- Tratamento de erros e fallbacks
- Integração com pipeline.nichos
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os


# ============================================================================
# Testes de _coletar_reddit_rss
# ============================================================================

@pytest.mark.asyncio
async def test_coletar_reddit_rss_sucesso():
    """Deve coletar posts de subreddits via RSS."""
    from services.trends.scraper import _coletar_reddit_rss

    # Mock do feedparser
    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [
        MagicMock(title="Post 1 do Reddit"),
        MagicMock(title="Post 2 do Reddit"),
        MagicMock(title="Post 3 do Reddit"),
    ]

    with patch("services.trends.scraper.feedparser.parse") as mock_parse:
        mock_parse.return_value = mock_feed

        titulos = await _coletar_reddit_rss("cultura_pop")

        assert len(titulos) > 0
        assert "Post 1 do Reddit" in titulos
        # Verificar que foi chamado para cada subreddit do nicho
        assert mock_parse.call_count >= 1


@pytest.mark.asyncio
async def test_coletar_reddit_rss_limite_por_subreddit():
    """Deve respeitar limite de posts por subreddit."""
    from services.trends.scraper import _coletar_reddit_rss

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [MagicMock(title=f"Post {i}") for i in range(10)]

    with patch("services.trends.scraper.feedparser.parse") as mock_parse:
        mock_parse.return_value = mock_feed

        titulos = await _coletar_reddit_rss("tecnologia", limite_por_subreddit=3)

        # 3 posts por subreddit, pelo menos 1 subreddit configurado
        assert len(titulos) >= 3


@pytest.mark.asyncio
async def test_coletar_reddit_rss_feed_erro():
    """Deve ignorar feeds com erro e continuar coletando de outros."""
    from services.trends.scraper import _coletar_reddit_rss

    # Primeiro feed com erro, segundo OK
    mock_feed_erro = MagicMock()
    mock_feed_erro.bozo = True
    mock_feed_erro.bozo_exception = Exception("Feed parse error")

    mock_feed_ok = MagicMock()
    mock_feed_ok.bozo = False
    mock_feed_ok.entries = [MagicMock(title="Post Válido")]

    with patch("services.trends.scraper.feedparser.parse") as mock_parse:
        mock_parse.side_effect = [mock_feed_erro, mock_feed_ok]

        titulos = await _coletar_reddit_rss("futebol")

        # Deve ter coletado do segundo subreddit mesmo com erro no primeiro
        assert "Post Válido" in titulos


@pytest.mark.asyncio
async def test_coletar_reddit_rss_nicho_nao_configurado():
    """Deve retornar lista vazia para nicho não configurado."""
    from services.trends.scraper import _coletar_reddit_rss

    with patch("pipeline.nichos.obter_config_nicho") as mock_config:
        mock_config.side_effect = ValueError("Nicho não existe")

        titulos = await _coletar_reddit_rss("nicho_inexistente")

        assert titulos == []


@pytest.mark.asyncio
async def test_coletar_reddit_rss_excecao_geral():
    """Deve retornar lista vazia em caso de exceção geral."""
    from services.trends.scraper import _coletar_reddit_rss

    with patch("services.trends.scraper.feedparser.parse") as mock_parse:
        mock_parse.side_effect = Exception("Erro de rede")

        titulos = await _coletar_reddit_rss("cultura_pop")

        assert titulos == []


# ============================================================================
# Testes de _coletar_youtube_trending
# ============================================================================

@pytest.mark.asyncio
async def test_coletar_youtube_trending_sucesso():
    """Deve coletar vídeos em tendência via YouTube API."""
    from services.trends.scraper import _coletar_youtube_trending

    # Mock da resposta da API
    mock_response = {
        "items": [
            {"snippet": {"title": "Vídeo Trending 1"}},
            {"snippet": {"title": "Vídeo Trending 2"}},
            {"snippet": {"title": "Vídeo Trending 3"}},
        ]
    }

    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = mock_response
    mock_youtube.videos().list.return_value = mock_request

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-api-key"}):
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_build.return_value = mock_youtube

            titulos = await _coletar_youtube_trending("cultura_pop")

            assert len(titulos) == 3
            assert "Vídeo Trending 1" in titulos
            mock_build.assert_called_once()


@pytest.mark.asyncio
async def test_coletar_youtube_trending_sem_api_key():
    """Deve retornar lista vazia se YOUTUBE_API_KEY não configurada."""
    from services.trends.scraper import _coletar_youtube_trending

    with patch.dict(os.environ, {}, clear=True):
        # Remover YOUTUBE_API_KEY se existir
        os.environ.pop("YOUTUBE_API_KEY", None)

        titulos = await _coletar_youtube_trending("tecnologia")

        assert titulos == []


@pytest.mark.asyncio
async def test_coletar_youtube_trending_erro_api():
    """Deve retornar lista vazia em caso de erro da API."""
    from services.trends.scraper import _coletar_youtube_trending
    from googleapiclient.errors import HttpError

    mock_response = MagicMock()
    mock_response.status = 403

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-api-key"}):
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_build.return_value.videos().list.side_effect = HttpError(
                mock_response, b'{"error": {"message": "Quota exceeded"}}'
            )

            titulos = await _coletar_youtube_trending("cultura_pop")

            assert titulos == []


@pytest.mark.asyncio
async def test_coletar_youtube_trending_limite():
    """Deve respeitar limite de vídeos."""
    from services.trends.scraper import _coletar_youtube_trending

    mock_response = {
        "items": [{"snippet": {"title": f"Vídeo {i}"}} for i in range(20)]
    }

    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = mock_response
    mock_youtube.videos().list.return_value = mock_request

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-api-key"}):
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_build.return_value = mock_youtube

            titulos = await _coletar_youtube_trending("tecnologia", limite=5)

            # Verificar que maxResults=5 foi passado
            call_kwargs = mock_youtube.videos().list.call_args[1]
            assert call_kwargs["maxResults"] == 5


@pytest.mark.asyncio
async def test_coletar_youtube_trending_resposta_vazia():
    """Deve lidar com resposta vazia da API."""
    from services.trends.scraper import _coletar_youtube_trending

    mock_response = {"items": []}

    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = mock_response
    mock_youtube.videos().list.return_value = mock_request

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-api-key"}):
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_build.return_value = mock_youtube

            titulos = await _coletar_youtube_trending("futebol")

            assert titulos == []


@pytest.mark.asyncio
async def test_coletar_youtube_trending_categoria_por_nicho():
    """Deve usar categoria correta para cada nicho."""
    from services.trends.scraper import _coletar_youtube_trending

    mock_response = {"items": [{"snippet": {"title": "Test"}}]}
    mock_youtube = MagicMock()
    mock_request = MagicMock()
    mock_request.execute.return_value = mock_response
    mock_youtube.videos().list.return_value = mock_request

    with patch.dict(os.environ, {"YOUTUBE_API_KEY": "test-api-key"}):
        with patch("googleapiclient.discovery.build") as mock_build:
            mock_build.return_value = mock_youtube

            # Testar diferentes nichos
            await _coletar_youtube_trending("cultura_pop")
            call_kwargs = mock_youtube.videos().list.call_args[1]
            categoria_cultura = call_kwargs["videoCategoryId"]

            await _coletar_youtube_trending("tecnologia")
            call_kwargs = mock_youtube.videos().list.call_args[1]
            categoria_tech = call_kwargs["videoCategoryId"]

            # Categorias devem diferir por nicho
            assert categoria_cultura != categoria_tech


# ============================================================================
# Testes de integração com coletar_tendencias
# ============================================================================

@pytest.mark.asyncio
async def test_coletar_tendencias_integra_novas_fontes():
    """coletar_tendencias deve usar novas fontes em paralelo."""
    from services.trends.scraper import coletar_tendencias

    with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock) as mock_google, \
         patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock) as mock_reddit, \
         patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock) as mock_youtube:

        mock_google.return_value = ["Tendência Google 1"]
        mock_reddit.return_value = ["Post Reddit 1"]
        mock_youtube.return_value = ["Vídeo YouTube 1"]

        tendencias = await coletar_tendencias("cultura_pop")

        # Deve consolidar todas as fontes
        assert "Tendência Google 1" in tendencias
        assert "Post Reddit 1" in tendencias
        assert "Vídeo YouTube 1" in tendencias

        # Todas as fontes devem ser chamadas
        mock_google.assert_called_once_with("cultura_pop")
        mock_reddit.assert_called_once_with("cultura_pop")
        mock_youtube.assert_called_once_with("cultura_pop")


@pytest.mark.asyncio
async def test_coletar_tendencias_falha_isolada():
    """Falha em uma fonte não deve quebrar outras."""
    from services.trends.scraper import coletar_tendencias

    with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock) as mock_google, \
         patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock) as mock_reddit, \
         patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock) as mock_youtube:

        mock_google.return_value = ["Tendência Google"]
        mock_reddit.side_effect = Exception("Reddit fora do ar")
        mock_youtube.return_value = ["Vídeo YouTube"]

        tendencias = await coletar_tendencias("tecnologia")

        # Deve ter resultados das fontes que funcionaram
        assert "Tendência Google" in tendencias
        assert "Vídeo YouTube" in tendencias
