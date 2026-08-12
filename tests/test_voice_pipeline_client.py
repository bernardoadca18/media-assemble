"""
Testes do cliente HTTP para o pipeline de voz Kokoro+Seed-VC.
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock
import tempfile

from services.audio.voice_pipeline_client import (
    VoicePipelineClient,
    RunNameInvalido,
    GPUOcupada,
    PipelineInternoFalhou,
)
from pipeline.config import settings


class TestVoicePipelineClient:
    """Testes do cliente HTTP."""

    @pytest.mark.asyncio
    async def test_narrar_sucesso_primeira_tentativa(self):
        """Sucesso na primeira chamada à API."""
        client = VoicePipelineClient(
            base_url="http://test",
            timeout=300,
            max_retries=3,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.wav"

            # Mock da resposta HTTP 200
            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.content = b"fake_audio_data"
                mock_client.post.return_value = mock_response

                audio_path, tempo = await client.narrar(
                    texto="Teste de texto",
                    run_name="minha_voz_v1",
                    output_path=output_path,
                )

                assert audio_path == output_path
                assert audio_path.exists()
                assert audio_path.read_bytes() == b"fake_audio_data"
                assert tempo >= 0

    @pytest.mark.asyncio
    async def test_narrar_erro_400_run_name_invalido(self):
        """Erro 400 - run_name sem checkpoint treinado."""
        client = VoicePipelineClient(
            base_url="http://test",
            timeout=300,
            max_retries=3,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 400
            mock_response.json.return_value = {"detail": "run_name não encontrado"}
            mock_client.post.return_value = mock_response

            with pytest.raises(RunNameInvalido) as exc_info:
                await client.narrar(
                    texto="Teste",
                    run_name="voz_invalida",
                )

            assert "run_name inválido" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_narrar_erro_409_gpu_ocupada_retry(self):
        """Erro 409 - GPU ocupada, deve fazer retry."""
        client = VoicePipelineClient(
            base_url="http://test",
            timeout=300,
            max_retries=3,
            retry_delay=0.01,  # Acelera teste
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.wav"

            with patch("httpx.AsyncClient") as mock_client_class:
                mock_client = AsyncMock()
                mock_client_class.return_value.__aenter__.return_value = mock_client

                # Primeira chamada: 409 (GPU ocupada)
                # Segunda chamada: 200 (sucesso)
                mock_response_409 = MagicMock()
                mock_response_409.status_code = 409

                mock_response_200 = MagicMock()
                mock_response_200.status_code = 200
                mock_response_200.content = b"fake_audio_data"

                mock_client.post.side_effect = [mock_response_409, mock_response_200]

                audio_path, tempo = await client.narrar(
                    texto="Teste",
                    run_name="minha_voz_v1",
                    output_path=output_path,
                )

                # Deve ter tentado 2 vezes
                assert mock_client.post.call_count == 2
                assert audio_path.exists()

    @pytest.mark.asyncio
    async def test_narrar_erro_409_esgota_retries(self):
        """Erro 409 persistente após esgotar retries."""
        client = VoicePipelineClient(
            base_url="http://test",
            timeout=300,
            max_retries=2,
            retry_delay=0.01,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 409
            mock_client.post.return_value = mock_response

            with pytest.raises(GPUOcupada):
                await client.narrar(
                    texto="Teste",
                    run_name="minha_voz_v1",
                )

            # Deve ter tentado max_retries vezes
            assert mock_client.post.call_count == 2

    @pytest.mark.asyncio
    async def test_narrar_erro_500_falha_interna(self):
        """Erro 500 - falha interna do pipeline."""
        client = VoicePipelineClient(
            base_url="http://test",
            timeout=300,
            max_retries=3,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.json.return_value = {"detail": "Seed-VC timeout"}
            mock_client.post.return_value = mock_response

            with pytest.raises(PipelineInternoFalhou) as exc_info:
                await client.narrar(
                    texto="Teste",
                    run_name="minha_voz_v1",
                )

            assert "Erro interno no pipeline" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_narrar_timeout(self):
        """Timeout de rede."""
        import httpx

        client = VoicePipelineClient(
            base_url="http://test",
            timeout=1,
            max_retries=1,
        )

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.post.side_effect = httpx.TimeoutException("Timeout")

            with pytest.raises(PipelineInternoFalhou) as exc_info:
                await client.narrar(
                    texto="Teste",
                    run_name="minha_voz_v1",
                )

            assert "Timeout" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_narrar_texto_vazio(self):
        """Texto vazio deve lançar erro imediatamente."""
        client = VoicePipelineClient()

        with pytest.raises(RunNameInvalido) as exc_info:
            await client.narrar(
                texto="",
                run_name="minha_voz_v1",
            )

        assert "Texto não pode estar vazio" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_healthcheck_sucesso(self):
        """Healthcheck retorna True para serviço saudável."""
        client = VoicePipelineClient(base_url="http://test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            saudavel = await client.healthcheck()
            assert saudavel is True

    @pytest.mark.asyncio
    async def test_healthcheck_falha(self):
        """Healthcheck retorna False para serviço indisponível."""
        client = VoicePipelineClient(base_url="http://test")

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client

            mock_client.get.side_effect = Exception("Conexão recusada")

            saudavel = await client.healthcheck()
            assert saudavel is False


class TestIntegracaoVoicePipeline:
    """
    Testes de integração contra serviço real.

    Marcados para pular se o serviço não estiver disponível.
    """

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        True,  # Mudar para False para testar contra serviço real
        reason="Serviço de voz não está disponível em CI"
    )
    async def test_integracao_real_narrar(self):
        """Teste de integração contra serviço real rodando localmente."""
        client = VoicePipelineClient(
            base_url="http://localhost:9000",
            timeout=300,
        )

        # Verifica se serviço está saudável
        saudavel = await client.healthcheck()
        if not saudavel:
            pytest.skip("Serviço de voz não está rodando em localhost:9000")

        # Testa geração de áudio
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test_integration.wav"

            audio_path, tempo = await client.narrar(
                texto="Este é um teste de integração do pipeline de voz.",
                run_name="minha_voz_v1",
                output_path=output_path,
            )

            assert audio_path.exists()
            assert audio_path.stat().st_size > 0, "Áudio não pode estar vazio"
            print(f"\n✅ Teste de integração passou!")
            print(f"   Tempo de síntese: {tempo:.2f}s")
            print(f"   Tamanho do áudio: {audio_path.stat().st_size} bytes")
