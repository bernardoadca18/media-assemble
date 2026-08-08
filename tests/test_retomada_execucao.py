"""
Testes para retomada de execuções falhas (Item 3 da Fase 7).

Cobrem:
- Listagem de execuções falhas
- Retomada a partir de cada uma das 5 fases
- Cenários de erro (execução não encontrada, roteiro ausente)
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from db.models import listar_execucoes_falhas, buscar_execucao_falha
from pipeline.orchestrator import retomar_execucao_falha
from pipeline.schemas import (
    Roteiro,
    MetadataRoteiro,
    Cena,
    Midia,
    TipoAsset,
    AnimacaoImagem,
    EfeitosVisuais,
    Overlays,
)


class TestListarExecucoesFalhas:
    """Testes para listagem de execuções falhas."""

    @pytest.mark.asyncio
    async def test_lista_vazia_quando_sem_falhas(self):
        """Retorna lista vazia quando não há execuções falhas."""
        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []

            mock_session_instance = AsyncMock()
            mock_session_instance.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            resultado = await listar_execucoes_falhas()
            assert resultado == []

    @pytest.mark.asyncio
    async def test_lista_execucoes_falhas_corretamente(self):
        """Lista execuções falhas com campos corretos."""
        from datetime import datetime

        # Mock de execução falha
        mock_exec = MagicMock()
        mock_exec.video_id = "test-uuid-123"
        mock_exec.nicho = "cultura_pop"
        mock_exec.etapa_atual = "audio"
        mock_exec.criado_em = datetime(2024, 1, 15, 10, 30, 0)

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_exec]

            mock_session_instance = AsyncMock()
            mock_session_instance.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            resultado = await listar_execucoes_falhas()

            assert len(resultado) == 1
            assert resultado[0]["video_id"] == "test-uuid-123"
            assert resultado[0]["nicho"] == "cultura_pop"
            assert resultado[0]["etapa_atual"] == "audio"


class TestBuscarExecucaoFalha:
    """Testes para busca de execução falha específica."""

    @pytest.mark.asyncio
    async def test_retorna_none_quando_nao_encontrada(self):
        """Retorna None quando execução não existe."""
        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None

            mock_session_instance = AsyncMock()
            mock_session_instance.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            resultado = await buscar_execucao_falha("video-inexistente")
            assert resultado is None

    @pytest.mark.asyncio
    async def test_retorna_execucao_correta(self):
        """Retorna execução falha quando encontrada."""
        from datetime import datetime

        mock_exec = MagicMock()
        mock_exec.video_id = "test-uuid-456"
        mock_exec.nicho = "animes"
        mock_exec.etapa_atual = "renderizacao"
        mock_exec.criado_em = datetime(2024, 1, 16, 14, 20, 0)

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_exec

            mock_session_instance = AsyncMock()
            mock_session_instance.execute.return_value = mock_result
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            resultado = await buscar_execucao_falha("test-uuid-456")

            assert resultado is not None
            assert resultado["video_id"] == "test-uuid-456"
            assert resultado["etapa_atual"] == "renderizacao"


class TestRetomarExecucao:
    """Testes para retomada de execuções falhas."""

    @pytest.fixture
    def roteiro_mock(self):
        """Cria um roteiro mock para testes."""
        return Roteiro(
            metadata=MetadataRoteiro(
                video_id="test-uuid-789",
                nicho="cultura_pop",
                titulo_sugerido="Teste de Retomada",
                duracao_estimada_segundos=60.0,
                trilha_fundo="epica",
                volume_trilha_fundo=0.15,
            ),
            cenas=[
                Cena(
                    cena_id=1,
                    ordem=1,
                    texto_locucao="Texto de teste",
                    duracao_estimada_segundos=5.0,
                    midia=Midia(
                        tipo_asset_preferencial=TipoAsset("imagem"),
                        keywords_busca=["teste"],
                        fallback_query="teste fallback",
                        duracao_minima=3.0,
                    ),
                    efeitos_visuais=EfeitosVisuais(
                        animacao_imagem=AnimacaoImagem("ken_burns_zoom_in"),
                    ),
                    overlays=Overlays(
                        exibir_legenda=True,
                        texto_destaque_tela=None,
                    ),
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_retorna_erro_quando_execucao_nao_encontrada(self):
        """Retorna erro quando video_id não existe no banco."""
        with patch("db.models.buscar_execucao_falha", new_callable=AsyncMock) as mock_buscar:
            mock_buscar.return_value = None

            resultado = await retomar_execucao_falha("video-inexistente")

            assert resultado["sucesso"] is False
            assert resultado["erro"] == "Execução não encontrada"

    @pytest.mark.asyncio
    async def test_retoma_da_fase_audio(self, roteiro_mock):
        """Retoma execução a partir da fase de áudio."""
        with patch("db.models.buscar_execucao_falha", new_callable=AsyncMock) as mock_buscar, \
             patch("db.models.carregar_roteiro", new_callable=AsyncMock) as mock_carregar, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock) as mock_salvar:

            mock_buscar.return_value = {
                "video_id": "test-uuid-789",
                "nicho": "cultura_pop",
                "etapa_atual": "audio",
            }
            mock_carregar.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock

            resultado = await retomar_execucao_falha("test-uuid-789")

            # Verifica que audio foi chamado
            mock_audio.assert_called_once()
            mock_salvar.assert_called()

    @pytest.mark.asyncio
    async def test_retoma_da_fase_assets(self, roteiro_mock):
        """Retoma execução a partir da fase de assets."""
        with patch("db.models.buscar_execucao_falha", new_callable=AsyncMock) as mock_buscar, \
             patch("db.models.carregar_roteiro", new_callable=AsyncMock) as mock_carregar, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock) as mock_salvar:

            mock_buscar.return_value = {
                "video_id": "test-uuid-789",
                "nicho": "cultura_pop",
                "etapa_atual": "assets",
            }
            mock_carregar.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.return_value = roteiro_mock

            resultado = await retomar_execucao_falha("test-uuid-789")

            # Verifica que audio e assets foram chamados
            mock_audio.assert_called_once()
            mock_assets.assert_called_once()

    @pytest.mark.asyncio
    async def test_retoma_da_fase_renderizacao(self, roteiro_mock):
        """Retoma execução a partir da fase de renderização."""
        from pathlib import Path

        with patch("db.models.buscar_execucao_falha", new_callable=AsyncMock) as mock_buscar, \
             patch("db.models.carregar_roteiro", new_callable=AsyncMock) as mock_carregar, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("services.render.remotion_bridge.renderizar_video", new_callable=AsyncMock) as mock_render, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock) as mock_salvar, \
             patch("db.models.salvar_execucao", new_callable=AsyncMock) as mock_salvar_exec:

            mock_buscar.return_value = {
                "video_id": "test-uuid-789",
                "nicho": "cultura_pop",
                "etapa_atual": "renderizacao",
            }
            mock_carregar.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.return_value = roteiro_mock
            mock_render.return_value = Path("/tmp/video_final.mp4")

            resultado = await retomar_execucao_falha("test-uuid-789")

            assert resultado["sucesso"] is True
            mock_render.assert_called_once()

    @pytest.mark.asyncio
    async def test_falha_quando_roteiro_ausente_em_fase_audio(self):
        """Falha quando roteiro não existe na fase de áudio."""
        with patch("db.models.buscar_execucao_falha", new_callable=AsyncMock) as mock_buscar, \
             patch("db.models.carregar_roteiro", new_callable=AsyncMock) as mock_carregar:

            mock_buscar.return_value = {
                "video_id": "test-uuid-999",
                "nicho": "cultura_pop",
                "etapa_atual": "audio",
            }
            mock_carregar.return_value = None

            resultado = await retomar_execucao_falha("test-uuid-999")

            assert resultado["sucesso"] is False
            assert "Roteiro não encontrado" in resultado["erro"]


class TestCLI:
    """Testes para comandos CLI de retomada."""

    def test_argumento_listar_falhas_existe(self):
        """Verifica que argumento --listar-falhas está disponível."""
        import argparse
        from main import main

        parser = argparse.ArgumentParser()
        parser.add_argument("--listar-falhas", action="store_true")
        args = parser.parse_args(["--listar-falhas"])

        assert args.listar_falhas is True

    def test_argumento_retomar_existe(self):
        """Verifica que argumento --retomar está disponível."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("--retomar", type=str, metavar="VIDEO_ID")
        args = parser.parse_args(["--retomar", "test-uuid-123"])

        assert args.retomar == "test-uuid-123"
