"""
Testes para Subfase 8.9.1 — Fontes de tendência via RSS e Custom Search.

Valida:
- Coleta de feeds RSS específicos por nicho
- Filtragem por janela de tempo (48h)
- Cota diária do Google Custom Search API (100 buscas/dia)
- Tratamento de erros e feeds malformados
- Integração com scraper.coletar_tendencias
"""
import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

from services.trends.rss_sources import (
    coletar_rss_nicho,
    coletar_custom_search,
    _verificar_e_incrementar_cota_cse,
    _carregar_cota_diaria,
    _salvar_cota_diaria,
    FEEDS_RSS_POR_NICHO,
    COTA_CSE_FILE,
)


class TestColetarRssNicho:
    """Testa coleta de feeds RSS por nicho."""

    @pytest.mark.asyncio
    async def test_coletar_rss_nicho_valido(self):
        """Coleta posts de feeds RSS válidos."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            MagicMock(
                title="Post 1",
                published_parsed=(datetime.now(timezone.utc) - timedelta(hours=1)).timetuple()
            ),
            MagicMock(
                title="Post 2",
                published_parsed=(datetime.now(timezone.utc) - timedelta(hours=2)).timetuple()
            ),
        ]

        # Mock apenas um feed para evitar duplicação
        with patch.dict(FEEDS_RSS_POR_NICHO, {"tecnologia": ["https://test.com/feed"]}):
            with patch("services.trends.rss_sources.feedparser.parse", return_value=mock_feed):
                tendencias = await coletar_rss_nicho("tecnologia", limite_por_feed=5)

        assert len(tendencias) == 2
        assert "Post 1" in tendencias
        assert "Post 2" in tendencias

    @pytest.mark.asyncio
    async def test_coletar_rss_nicho_sem_feeds_configurados(self):
        """Retorna lista vazia para nicho sem feeds configurados."""
        tendencias = await coletar_rss_nicho("nicho_inexistente")
        assert tendencias == []

    @pytest.mark.asyncio
    async def test_coletar_rss_filtrar_por_data(self):
        """Filtra posts mais antigos que 48h."""
        mock_feed = MagicMock()
        mock_feed.bozo = False

        # Post recente (1 hora atrás)
        post_recente = MagicMock(
            title="Post Recente",
            published_parsed=(datetime.now(timezone.utc) - timedelta(hours=1)).timetuple()
        )

        # Post antigo (72 horas atrás - fora da janela)
        post_antigo = MagicMock(
            title="Post Antigo",
            published_parsed=(datetime.now(timezone.utc) - timedelta(hours=72)).timetuple()
        )

        mock_feed.entries = [post_recente, post_antigo]

        # Mock apenas um feed para evitar duplicação
        with patch.dict(FEEDS_RSS_POR_NICHO, {"tecnologia": ["https://test.com/feed"]}):
            with patch("services.trends.rss_sources.feedparser.parse", return_value=mock_feed):
                tendencias = await coletar_rss_nicho("tecnologia", limite_por_feed=10)

        # Apenas o post recente deve ser incluído
        assert len(tendencias) == 1
        assert "Post Recente" in tendencias
        assert "Post Antigo" not in tendencias

    @pytest.mark.asyncio
    async def test_coletar_rss_feed_malformado(self):
        """Trata feeds malformados (bozo_exception) e continua."""
        mock_feed_malformado = MagicMock()
        mock_feed_malformado.bozo = True
        mock_feed_malformado.bozo_exception = Exception("XML error")

        mock_feed_valido = MagicMock()
        mock_feed_valido.bozo = False
        mock_feed_valido.entries = [
            MagicMock(
                title="Post Válido",
                published_parsed=(datetime.now(timezone.utc) - timedelta(hours=1)).timetuple()
            )
        ]

        with patch("services.trends.rss_sources.feedparser.parse") as mock_parse:
            # Primeiro feed falha, segundo funciona
            mock_parse.side_effect = [mock_feed_malformado, mock_feed_valido]

            # Atualiza FEEDS_RSS_POR_NICHO para ter 2 feeds
            with patch.dict(FEEDS_RSS_POR_NICHO, {"tecnologia": ["feed1", "feed2"]}):
                tendencias = await coletar_rss_nicho("tecnologia", limite_por_feed=5)

        assert len(tendencias) == 1
        assert "Post Válido" in tendencias

    @pytest.mark.asyncio
    async def test_coletar_rss_erro_inesperado(self):
        """Continua mesmo com erro inesperado em um feed."""
        with patch("services.trends.rss_sources.feedparser.parse", side_effect=Exception("Network error")):
            tendencias = await coletar_rss_nicho("tecnologia", limite_por_feed=5)

        # Não deve quebrar, retorna lista vazia
        assert tendencias == []

    @pytest.mark.asyncio
    async def test_coletar_rss_sem_published_parsed(self):
        """Inclui posts sem data de publicação (assume como recente)."""
        mock_feed = MagicMock()
        mock_feed.bozo = False
        mock_feed.entries = [
            MagicMock(title="Post Sem Data"),  # Sem published_parsed
        ]

        # Mock apenas um feed para evitar duplicação
        with patch.dict(FEEDS_RSS_POR_NICHO, {"tecnologia": ["https://test.com/feed"]}):
            with patch("services.trends.rss_sources.feedparser.parse", return_value=mock_feed):
                tendencias = await coletar_rss_nicho("tecnologia", limite_por_feed=5)

        assert len(tendencias) == 1
        assert "Post Sem Data" in tendencias


class TestCotaDiariaCSE:
    """Testa gerenciamento de cota diária do Custom Search API."""

    def test_carregar_cota_arquivo_inexistente(self):
        """Retorna dict vazio se arquivo de cota não existe."""
        with patch("builtins.open", side_effect=FileNotFoundError):
            cota = _carregar_cota_diaria()
        assert cota == {}

    def test_carregar_cota_json_invalido(self):
        """Retorna dict vazio se JSON está malformado."""
        with patch("builtins.open", mock_open(read_data="não é json")):
            cota = _carregar_cota_diaria()
        assert cota == {}

    def test_salvar_cota_sucesso(self):
        """Salva cota no arquivo."""
        cota = {"data": "2026-08-08", "contador": 5}

        with patch("builtins.open", mock_open()) as mock_file:
            _salvar_cota_diaria(cota)

            # Verifica que open foi chamado para escrita
            mock_file.assert_called_once_with(COTA_CSE_FILE, "w")
            # Verifica que json.dump foi escrito
            handle = mock_file()
            # json.dump escreve múltiplas vezes, então verificamos que houve escrita
            assert handle.write.call_count > 0

    def test_verificar_e_incrementar_cota_sem_api_key(self):
        """Retorna False se API key não está configurada."""
        with patch.dict(os.environ, {}, clear=True):
            resultado = _verificar_e_incrementar_cota_cse()
        assert resultado is False

    def test_verificar_e_incrementar_cota_primeira_chamada(self):
        """Incrementa cota na primeira chamada do dia."""
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._carregar_cota_diaria", return_value={}):
                with patch("services.trends.rss_sources._salvar_cota_diaria") as mock_salvar:
                    resultado = _verificar_e_incrementar_cota_cse()

        assert resultado is True
        mock_salvar.assert_called_once()
        # Verifica que contador foi incrementado
        cota_salva = mock_salvar.call_args[0][0]
        assert cota_salva["contador"] == 1

    def test_verificar_e_incrementar_cota_reseta_dia_novo(self):
        """Reseta contador quando dia muda."""
        ontem = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._carregar_cota_diaria", return_value={"data": ontem, "contador": 99}):
                with patch("services.trends.rss_sources._salvar_cota_diaria") as mock_salvar:
                    resultado = _verificar_e_incrementar_cota_cse()

        assert resultado is True
        cota_salva = mock_salvar.call_args[0][0]
        assert cota_salva["contador"] == 1  # Resetou

    def test_verificar_e_incrementar_cota_limite_atingido(self):
        """Retorna False quando limite diário é atingido."""
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._carregar_cota_diaria", return_value={"data": hoje, "contador": 100}):
                resultado = _verificar_e_incrementar_cota_cse()

        assert resultado is False

    def test_verificar_e_incrementar_cota_incrementa(self):
        """Incrementa contador existente."""
        hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._carregar_cota_diaria", return_value={"data": hoje, "contador": 50}):
                with patch("services.trends.rss_sources._salvar_cota_diaria") as mock_salvar:
                    resultado = _verificar_e_incrementar_cota_cse()

        assert resultado is True
        cota_salva = mock_salvar.call_args[0][0]
        assert cota_salva["contador"] == 51


class TestColetarCustomSearch:
    """Testa coleta via Google Custom Search API."""

    @pytest.mark.asyncio
    async def test_custom_search_sem_api_key(self):
        """Retorna lista vazia se API key não configurada."""
        with patch.dict(os.environ, {}, clear=True):
            tendencias = await coletar_custom_search("tecnologia")
        assert tendencias == []

    @pytest.mark.asyncio
    async def test_custom_search_cota_excedida(self):
        """Retorna lista vazia se cota diária excedida."""
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._verificar_e_incrementar_cota_cse", return_value=False):
                tendencias = await coletar_custom_search("tecnologia")
        assert tendencias == []

    @pytest.mark.asyncio
    async def test_custom_search_sucesso(self):
        """Coleta títulos via Custom Search API."""
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._verificar_e_incrementar_cota_cse", return_value=True):
                # Criar mock para o response
                mock_response = AsyncMock()
                mock_response.status = 200
                mock_response.json = AsyncMock(return_value={
                    "items": [
                        {"title": "Resultado 1"},
                        {"title": "Resultado 2"},
                    ]
                })

                # Criar mock do context manager para session.get()
                mock_get_context = AsyncMock()
                mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
                mock_get_context.__aexit__ = AsyncMock(return_value=None)

                # Criar mock da sessão
                mock_session = AsyncMock()
                mock_session.get = MagicMock(return_value=mock_get_context)
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)

                with patch("aiohttp.ClientSession", return_value=mock_session):
                    tendencias = await coletar_custom_search("tecnologia", limite=5)

        assert len(tendencias) == 2
        assert "Resultado 1" in tendencias
        assert "Resultado 2" in tendencias

    @pytest.mark.asyncio
    async def test_custom_search_erro_403(self):
        """Trata erro de quota excedida (403)."""
        mock_response = AsyncMock()
        mock_response.status = 403

        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._verificar_e_incrementar_cota_cse", return_value=True):
                mock_session_instance = MagicMock()
                mock_session_instance.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_session_instance.get.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch("aiohttp.ClientSession", return_value=mock_session_instance):
                    mock_session_instance.get = MagicMock(return_value=MagicMock(
                        __aenter__=AsyncMock(return_value=mock_response),
                        __aexit__=AsyncMock(return_value=None)
                    ))

                    tendencias = await coletar_custom_search("tecnologia")

        assert tendencias == []

    @pytest.mark.asyncio
    async def test_custom_search_erro_inesperado(self):
        """Trata erros inesperados."""
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._verificar_e_incrementar_cota_cse", return_value=True):
                with patch("aiohttp.ClientSession", side_effect=Exception("Network error")):
                    tendencias = await coletar_custom_search("tecnologia")

        assert tendencias == []

    @pytest.mark.asyncio
    async def test_custom_search_sem_itens(self):
        """Trata resposta sem itens."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={})

        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "key", "GOOGLE_CSE_ID": "id"}):
            with patch("services.trends.rss_sources._verificar_e_incrementar_cota_cse", return_value=True):
                mock_session_instance = MagicMock()
                mock_session_instance.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_session_instance.get.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch("aiohttp.ClientSession", return_value=mock_session_instance):
                    mock_session_instance.get = MagicMock(return_value=MagicMock(
                        __aenter__=AsyncMock(return_value=mock_response),
                        __aexit__=AsyncMock(return_value=None)
                    ))

                    tendencias = await coletar_custom_search("tecnologia")

        assert tendencias == []


class TestIntegracaoScraper:
    """Testa integração das novas fontes no scraper."""

    @pytest.mark.asyncio
    async def test_coletar_tendencias_integra_rss_nicho(self):
        """Verifica que coletar_tendencias chama coletar_rss_nicho."""
        from services.trends.scraper import coletar_tendencias

        with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock, return_value=["Trend 1"]):
            with patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock, return_value=["Trend 2"]):
                with patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock, return_value=["Trend 3"]):
                    with patch("services.trends.rss_sources.coletar_rss_nicho", new_callable=AsyncMock, return_value=["RSS 1"]) as mock_rss:
                        with patch("services.trends.rss_sources.coletar_custom_search", new_callable=AsyncMock, return_value=["CSE 1"]):
                            tendencias = await coletar_tendencias("tecnologia")

        mock_rss.assert_called_once_with("tecnologia")
        assert "RSS 1" in tendencias

    @pytest.mark.asyncio
    async def test_coletar_tendencias_integra_custom_search(self):
        """Verifica que coletar_tendencias chama coletar_custom_search."""
        from services.trends.scraper import coletar_tendencias

        with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock, return_value=[]):
            with patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock, return_value=[]):
                with patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock, return_value=[]):
                    with patch("services.trends.rss_sources.coletar_rss_nicho", new_callable=AsyncMock, return_value=[]):
                        with patch("services.trends.rss_sources.coletar_custom_search", new_callable=AsyncMock, return_value=["CSE 1"]) as mock_cse:
                            tendencias = await coletar_tendencias("cultura_pop")

        mock_cse.assert_called_once_with("cultura_pop")
        assert "CSE 1" in tendencias

    @pytest.mark.asyncio
    async def test_coletar_tendencias_remove_duplicatas(self):
        """Remove duplicatas de múltiplas fontes."""
        from services.trends.scraper import coletar_tendencias

        with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock, return_value=["Tema A", "Tema B"]):
            with patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock, return_value=["Tema B", "Tema C"]):
                with patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock, return_value=["Tema A"]):
                    with patch("services.trends.rss_sources.coletar_rss_nicho", new_callable=AsyncMock, return_value=["Tema D"]):
                        with patch("services.trends.rss_sources.coletar_custom_search", new_callable=AsyncMock, return_value=["Tema D"]):
                            tendencias = await coletar_tendencias("tecnologia")

        # Deve remover duplicatas mas preservar ordem
        assert tendencias.count("Tema A") == 1
        assert tendencias.count("Tema B") == 1
        assert tendencias.count("Tema D") == 1

    @pytest.mark.asyncio
    async def test_coletar_tendencias_fonte_falha_nao_quebra(self):
        """Fonte com exceção não quebra o pipeline."""
        from services.trends.scraper import coletar_tendencias

        with patch("services.trends.scraper._coletar_google_trends", new_callable=AsyncMock, return_value=["Trend 1"]):
            with patch("services.trends.scraper._coletar_reddit_rss", new_callable=AsyncMock, side_effect=Exception("Reddit error")):
                with patch("services.trends.scraper._coletar_youtube_trending", new_callable=AsyncMock, return_value=["Trend 2"]):
                    with patch("services.trends.rss_sources.coletar_rss_nicho", new_callable=AsyncMock, return_value=[]):
                        with patch("services.trends.rss_sources.coletar_custom_search", new_callable=AsyncMock, return_value=[]):
                            tendencias = await coletar_tendencias("cultura_pop")

        # Deve retornar tendências das fontes que funcionaram
        assert "Trend 1" in tendencias
        assert "Trend 2" in tendencias
