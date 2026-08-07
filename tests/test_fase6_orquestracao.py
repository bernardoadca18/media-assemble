"""Testes para a Fase 6: Orquestração End-to-End, Agendamento e Observabilidade."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path

from pipeline.schemas import Ideia, Roteiro, MetadataRoteiro, Cena, Palavra
from db.models import salvar_execucao, ExecucaoPipeline


class TestSalvarExecucao:
    """Testes para persistência de execuções do pipeline."""

    @pytest.mark.asyncio
    async def test_criar_novo_registro(self):
        """Testa criação de um novo registro de execução."""
        mock_session = AsyncMock()

        # Configurar execute para retornar um result que retorna None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        with patch("db.models.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            await salvar_execucao(
                video_id="test_video_123",
                nicho="cultura_pop",
                etapa_atual="audio",
                sucesso=False,
            )

            # Verificar que add foi chamado com um ExecucaoPipeline
            mock_session.add.assert_called_once()
            registro = mock_session.add.call_args[0][0]
            assert isinstance(registro, ExecucaoPipeline)
            assert registro.video_id == "test_video_123"
            assert registro.nicho == "cultura_pop"
            assert registro.etapa_atual == "audio"
            assert registro.sucesso is False

    @pytest.mark.asyncio
    async def test_upsert_registro_existente(self):
        """Testa atualização de um registro existente (upsert por video_id)."""
        mock_session = AsyncMock()

        # Simular registro existente
        registro_existente = ExecucaoPipeline(
            video_id="test_video_123",
            nicho="cultura_pop",
            etapa_atual="audio",
            sucesso=None,
        )

        # Configurar execute para retornar o registro existente
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = registro_existente
        mock_session.execute.return_value = mock_result

        with patch("db.models.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            await salvar_execucao(
                video_id="test_video_123",
                nicho="cultura_pop",
                etapa_atual="renderizacao",
                sucesso=True,
                caminho_video_final="/data/videos/test_video_123.mp4",
                wer_medio=0.05,
            )

            # Verificar que não criou novo registro
            mock_session.add.assert_not_called()
            # Verificar atualização
            assert registro_existente.etapa_atual == "renderizacao"
            assert registro_existente.sucesso is True
            assert registro_existente.caminho_video_final == "/data/videos/test_video_123.mp4"
            assert registro_existente.wer_medio == 0.05

    @pytest.mark.asyncio
    async def test_registro_sem_video_id(self):
        """Testa criação de registro quando video_id é None (ex: falha na ideação)."""
        mock_session = AsyncMock()

        with patch("db.models.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            await salvar_execucao(
                video_id=None,
                nicho="cultura_pop",
                etapa_atual="ideacao",
                sucesso=False,
            )

            mock_session.add.assert_called_once()
            registro = mock_session.add.call_args[0][0]
            assert registro.video_id == ""  # String vazia quando None
            assert registro.etapa_atual == "ideacao"


class TestTratamentoErrosOrquestrador:
    """Testes para tratamento de erros por etapa no pipeline."""

    def _criar_roteiro_mock(self, video_id: str = "test_video_123"):
        """Helper para criar roteiro mockado."""
        from pipeline.schemas import Midia, EfeitosVisuais, Overlays, TipoAsset, AnimacaoImagem

        return Roteiro(
            metadata=MetadataRoteiro(
                video_id=video_id,
                nicho="cultura_pop",
                titulo_sugerido="Teste",
                duracao_estimada_segundos=60.0,
                trilha_fundo="epic",
            ),
            cenas=[
                Cena(
                    cena_id=1,
                    ordem=1,
                    texto_locucao="Texto de teste",
                    duracao_estimada_segundos=5.0,
                    midia=Midia(
                        tipo_asset_preferencial=TipoAsset.imagem,
                        keywords_busca=["teste"],
                        fallback_query="teste fallback",
                        duracao_minima=3.0,
                    ),
                    efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
                    overlays=Overlays(),
                    palavras_transcritas=[Palavra(text="teste", start=0.0, end=0.5)],
                    wer_final=0.05,
                )
            ],
        )

    @pytest.mark.asyncio
    async def test_falha_na_ideacao_registra_e_nao_propaga(self):
        """Testa que falha na Fase 1 é capturada e não propaga exceção."""
        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar:

            mock_ideacao.side_effect = Exception("Erro na API de tendências")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            # Verificar que retornou estrutura de erro
            assert resultado is not None
            assert resultado.get("sucesso") is False
            assert resultado.get("etapa") == "ideacao"
            assert "Erro na API de tendências" in resultado.get("erro", "")

            # Verificar que salvou execução com falha
            mock_salvar.assert_called_once()
            call_kwargs = mock_salvar.call_args[1]
            assert call_kwargs["etapa_atual"] == "ideacao"
            assert call_kwargs["sucesso"] is False

    @pytest.mark.asyncio
    async def test_falha_na_roteirizacao_registra_com_video_id_none(self):
        """Testa que falha na Fase 2 é capturada com video_id None (ainda não gerado)."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar:

            mock_ideacao.return_value = ideias_mock
            mock_roteiro.side_effect = Exception("Erro no LLM de roteirização")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            assert resultado.get("sucesso") is False
            assert resultado.get("etapa") == "roteirizacao"

            call_kwargs = mock_salvar.call_args[1]
            assert call_kwargs["etapa_atual"] == "roteirizacao"
            assert call_kwargs["sucesso"] is False

    @pytest.mark.asyncio
    async def test_falha_na_audio_registra_com_video_id(self):
        """Testa que falha na Fase 3 captura o video_id corretamente."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]
        roteiro_mock = self._criar_roteiro_mock()

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):

            mock_ideacao.return_value = ideias_mock
            mock_roteiro.return_value = roteiro_mock
            mock_audio.side_effect = Exception("Erro no TTS")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            assert resultado.get("sucesso") is False
            assert resultado.get("etapa") == "audio"
            assert resultado.get("video_id") == "test_video_123"

    @pytest.mark.asyncio
    async def test_falha_na_assets_registra_com_video_id(self):
        """Testa que falha na Fase 4 captura o video_id corretamente."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]
        roteiro_mock = self._criar_roteiro_mock()
        roteiro_mock.metadata.audio_final_path = "/tmp/audio.wav"

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):

            mock_ideacao.return_value = ideias_mock
            mock_roteiro.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.side_effect = Exception("Erro ao baixar do Pexels")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            assert resultado.get("sucesso") is False
            assert resultado.get("etapa") == "assets"
            assert resultado.get("video_id") == "test_video_123"

    @pytest.mark.asyncio
    async def test_falha_na_renderizacao_registra_com_video_id(self):
        """Testa que falha na Fase 5 captura o video_id corretamente."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]
        roteiro_mock = self._criar_roteiro_mock()
        roteiro_mock.metadata.audio_final_path = "/tmp/audio.wav"
        roteiro_mock.cenas[0].asset_resolvido_path = "/tmp/asset.jpg"

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("services.render.remotion_bridge.renderizar_video", new_callable=AsyncMock) as mock_render, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):

            mock_ideacao.return_value = ideias_mock
            mock_roteiro.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.return_value = roteiro_mock
            mock_render.side_effect = Exception("Erro no ffmpeg")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            assert resultado.get("sucesso") is False
            assert resultado.get("etapa") == "renderizacao"
            assert resultado.get("video_id") == "test_video_123"

    @pytest.mark.asyncio
    async def test_execucao_apos_falha_funciona_normalmente(self):
        """Testa que uma chamada após falha simulada funciona sem estado travado."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]
        roteiro_mock = self._criar_roteiro_mock("video_sucesso")
        roteiro_mock.metadata.audio_final_path = "/tmp/audio.wav"
        roteiro_mock.cenas[0].asset_resolvido_path = "/tmp/asset.jpg"

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("services.render.remotion_bridge.renderizar_video", new_callable=AsyncMock) as mock_render, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):

            # Primeira chamada: falha
            mock_ideacao.side_effect = Exception("Falha proposital")
            from pipeline.orchestrator import rodar_pipeline_completo
            resultado1 = await rodar_pipeline_completo("cultura_pop")
            assert resultado1.get("sucesso") is False

            # Segunda chamada: sucesso
            mock_ideacao.side_effect = None
            mock_ideacao.return_value = ideias_mock
            mock_roteiro.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.return_value = roteiro_mock
            mock_render.return_value = Path("/tmp/video_final.mp4")

            resultado2 = await rodar_pipeline_completo("cultura_pop")
            assert resultado2.get("sucesso") is True
            assert resultado2.get("video_id") == "video_sucesso"

    @pytest.mark.asyncio
    async def test_execucao_bem_sucedida_registra_wer_medio(self):
        """Testa que execução bem-sucedida calcula e registra WER médio."""
        ideias_mock = [Ideia(topico="Teste", titulo_sugerido="Titulo", descricao_breve="Desc")]
        roteiro_mock = self._criar_roteiro_mock()
        roteiro_mock.metadata.audio_final_path = "/tmp/audio.wav"
        roteiro_mock.cenas[0].asset_resolvido_path = "/tmp/asset.jpg"
        # O wer_final já está definido no helper como 0.05

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock) as mock_ideacao, \
             patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock) as mock_roteiro, \
             patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock) as mock_audio, \
             patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock) as mock_assets, \
             patch("services.render.remotion_bridge.renderizar_video", new_callable=AsyncMock) as mock_render, \
             patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock) as mock_salvar, \
             patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):

            mock_ideacao.return_value = ideias_mock
            mock_roteiro.return_value = roteiro_mock
            mock_audio.return_value = roteiro_mock
            mock_assets.return_value = roteiro_mock
            mock_render.return_value = Path("/tmp/video_final.mp4")

            from pipeline.orchestrator import rodar_pipeline_completo
            resultado = await rodar_pipeline_completo("cultura_pop")

            assert resultado.get("sucesso") is True

            # Verificar que salvou execução com sucesso e WER
            calls = mock_salvar.call_args_list
            ultima_chamada = calls[-1][1]
            assert ultima_chamada["sucesso"] is True
            assert ultima_chamada["etapa_atual"] == "renderizacao"
            assert ultima_chamada["wer_medio"] == 0.05
