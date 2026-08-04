"""
Testes para a Fase 5 - Bridge Python -> Remotion.
"""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest

from pipeline.schemas import (
    Roteiro,
    MetadataRoteiro,
    Cena,
    Midia,
    EfeitosVisuais,
    Overlays,
    AnimacaoImagem,
    TipoAsset,
    Palavra,
)
from services.render.remotion_bridge import renderizar_video, _executar_comando_remotion


@pytest.fixture
def roteiro_exemplo() -> Roteiro:
    """Cria um roteiro de exemplo para testes."""
    metadata = MetadataRoteiro(
        video_id="test_video_123",
        nicho="tecnologia",
        titulo_sugerido="Como a IA está mudando o mundo",
        duracao_estimada_segundos=60.0,
        trilha_fundo="/data/audio/trilha_fundo.mp3",
        volume_trilha_fundo=0.15,
        audio_final_path="/data/audio/narracao_final.mp3",
        palavras_transcritas=[
            Palavra(text="Olá", start=0.0, end=0.5),
            Palavra(text="mundo", start=0.5, end=1.0),
        ],
    )

    cena = Cena(
        cena_id=1,
        ordem=1,
        texto_locucao="Esta é uma cena de teste.",
        duracao_estimada_segundos=5.0,
        midia=Midia(
            tipo_asset_preferencial=TipoAsset.imagem,
            keywords_busca=["tecnologia", "ia"],
            fallback_query="technology artificial intelligence",
            duracao_minima=5.0,
        ),
        efeitos_visuais=EfeitosVisuais(
            animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            transicao_saida="fade",
            duracao_transicao_segundos=0.5,
        ),
        overlays=Overlays(
            exibir_legenda=True,
            texto_destaque_tela=None,
        ),
        audio_path="/data/audio/cena_1.mp3",
        palavras_transcritas=[
            Palavra(text="Esta", start=0.0, end=0.2),
            Palavra(text="é", start=0.2, end=0.3),
        ],
        asset_resolvido_path="/data/assets/imagem_1.jpg",
        asset_origem="banco_local",
    )

    return Roteiro(metadata=metadata, cenas=[cena])


class TestSerializacaoRoteiro:
    """Testa a serialização do roteiro para JSON."""

    def test_serializacao_roteiro_valido(self, roteiro_exemplo):
        """Verifica se o roteiro é serializado corretamente."""
        json_str = roteiro_exemplo.model_dump_json()
        data = json.loads(json_str)

        assert data["metadata"]["video_id"] == "test_video_123"
        assert data["metadata"]["titulo_sugerido"] == "Como a IA está mudando o mundo"
        assert len(data["cenas"]) == 1
        assert data["cenas"][0]["cena_id"] == 1

    def test_serializacao_preserva_campos_aninhados(self, roteiro_exemplo):
        """Verifica se campos aninhados são preservados."""
        json_str = roteiro_exemplo.model_dump_json()
        data = json.loads(json_str)

        cena = data["cenas"][0]
        assert cena["efeitos_visuais"]["animacao_imagem"] == "ken_burns_zoom_in"
        assert cena["overlays"]["exibir_legenda"] is True

    def test_serializacao_lista_palavras(self, roteiro_exemplo):
        """Verifica se a lista de palavras transcritas é serializada."""
        json_str = roteiro_exemplo.model_dump_json()
        data = json.loads(json_str)

        palavras = data["metadata"]["palavras_transcritas"]
        assert len(palavras) == 2
        assert palavras[0]["text"] == "Olá"
        assert palavras[0]["start"] == 0.0
        assert palavras[0]["end"] == 0.5


class TestMontagemComando:
    """Testa a montagem do comando subprocess."""

    def test_executar_comando_sucesso(self):
        """Testa execução bem-sucedida do comando."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "Render completed successfully"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            resultado = _executar_comando_remotion(
                ["npx", "remotion", "render", "VideoPrincipal", "out.mp4"],
                Path("/tmp/remotion")
            )

            assert resultado["returncode"] == 0
            assert "Render completed" in resultado["stdout"]

    def test_executar_comando_falha(self):
        """Testa tratamento de erro na execução."""
        with patch("subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: Input file not found"
            mock_run.return_value = mock_result

            resultado = _executar_comando_remotion(
                ["npx", "remotion", "render", "VideoPrincipal", "out.mp4"],
                Path("/tmp/remotion")
            )

            assert resultado["returncode"] == 1
            assert "Error" in resultado["stderr"]

    def test_executar_comando_timeout(self):
        """Testa tratamento de timeout."""
        import subprocess

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd="npx remotion render",
                timeout=600
            )

            resultado = _executar_comando_remotion(
                ["npx", "remotion", "render", "VideoPrincipal", "out.mp4"],
                Path("/tmp/remotion")
            )

            assert resultado["returncode"] == -1
            assert "Timeout" in resultado["stderr"]


class TestTratamentoErro:
    """Testa tratamento de erros na renderização."""

    @pytest.mark.asyncio
    async def test_renderizar_video_erro_subprocess(self, roteiro_exemplo):
        """Testa tratamento de erro quando subprocess falha."""
        with patch("services.render.remotion_bridge._executar_comando_remotion") as mock_exec:
            mock_exec.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "Remotion error",
            }

            with pytest.raises(RuntimeError, match="Falha ao renderizar vídeo"):
                await renderizar_video(roteiro_exemplo)

    @pytest.mark.asyncio
    async def test_renderizar_video_timeout(self, roteiro_exemplo):
        """Testa tratamento de timeout na renderização."""
        with patch("services.render.remotion_bridge._executar_comando_remotion") as mock_exec:
            mock_exec.return_value = {
                "returncode": -1,
                "stdout": "",
                "stderr": "Timeout: renderização excedeu 10 minutos",
            }

            with pytest.raises(RuntimeError, match="Timeout"):
                await renderizar_video(roteiro_exemplo)

    @pytest.mark.asyncio
    async def test_arquivo_temporario_limpo_erro(self, roteiro_exemplo):
        """Verifica se arquivo temporário é limpo mesmo com erro."""
        with patch("services.render.remotion_bridge._executar_comando_remotion") as mock_exec:
            mock_exec.return_value = {
                "returncode": 1,
                "stdout": "",
                "stderr": "Error",
            }

            temp_files_before = set(Path(tempfile.gettempdir()).glob("roteiro_*"))

            with pytest.raises(RuntimeError):
                await renderizar_video(roteiro_exemplo)

            temp_files_after = set(Path(tempfile.gettempdir()).glob("roteiro_*"))

            # Verifica que não sobrou arquivo temporário
            assert temp_files_before == temp_files_after


class TestIntegracao:
    """Testes de integração (mockados)."""

    @pytest.mark.asyncio
    async def test_renderizar_video_sucesso(self, roteiro_exemplo, tmp_path):
        """Testa fluxo completo de renderização (mockado)."""
        output_file = tmp_path / "video_final.mp4"

        with patch("services.render.remotion_bridge._executar_comando_remotion") as mock_exec:
            mock_exec.return_value = {
                "returncode": 0,
                "stdout": "Render completed",
                "stderr": "",
            }

            # Criar arquivo de saída fake
            output_file.touch()

            resultado = await renderizar_video(roteiro_exemplo, output_path=output_file)

            # Verificar que o comando foi chamado com os argumentos corretos
            assert mock_exec.called
            args = mock_exec.call_args[0][0]
            assert "npx" in args
            assert "remotion" in args
            assert "render" in args
            assert "--concurrency=1" in args

    @pytest.mark.asyncio
    async def test_renderizar_video_path_padrao(self, roteiro_exemplo):
        """Testa que o path padrão é usado quando não especificado."""
        with patch("services.render.remotion_bridge._executar_comando_remotion") as mock_exec:
            mock_exec.return_value = {
                "returncode": 0,
                "stdout": "OK",
                "stderr": "",
            }

            # Patch para criar diretório
            with patch("pathlib.Path.mkdir"):
                with patch("pathlib.Path.touch"):
                    resultado = await renderizar_video(roteiro_exemplo)

                    # Verificar que o path padrão foi usado
                    assert "test_video_123" in str(resultado)
                    assert resultado.suffix == ".mp4"
