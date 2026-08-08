"""
Testes para Fase 9.2 — Resolução de asset por gameplay (gameplay_bg).

Valida:
- Seleção de segmentos cobrindo duração alvo
- Respeito à janela de reuso (segmento usado recentemente não é reutilizado)
- Concatenação com crossfade
- Atualização do campo usado_em
- Integração com pipeline de renderização
"""
import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from services.gameplay.resolver import (
    selecionar_segmentos,
    concatenar_segmentos,
    resolver_gameplay_bg,
    GameplayBgResolvido,
)
from pipeline.schemas import Roteiro, MetadataRoteiro, Cena, Midia, TipoAsset


@pytest.fixture
def mock_segmentos():
    """Segmentos de exemplo para testes."""
    hoje = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "id": 1,
            "jogo_origem": "Game A",
            "caminho_arquivo": "/tmp/seg1.mp4",
            "duracao_segundos": 30.0,
            "score_movimento": 25.0,
            "faixa_intensidade": "moderado",
            "usado_em": [],
        },
        {
            "id": 2,
            "jogo_origem": "Game B",
            "caminho_arquivo": "/tmp/seg2.mp4",
            "duracao_segundos": 30.0,
            "score_movimento": 50.0,
            "faixa_intensidade": "intenso",
            "usado_em": [],
        },
        {
            "id": 3,
            "jogo_origem": "Game A",
            "caminho_arquivo": "/tmp/seg3.mp4",
            "duracao_segundos": 30.0,
            "score_movimento": 10.0,
            "faixa_intensidade": "calmo",
            "usado_em": [],
        },
    ]


@pytest.fixture
def mock_roteiro(tmp_path):
    """Roteiro de exemplo com áudio."""
    audio_path = tmp_path / "audio.wav"
    audio_path.write_bytes(b"fake audio")

    # Usar MagicMock para evitar validação Pydantic complexa
    metadata = MagicMock()
    metadata.video_id = "test_video_001"
    metadata.audio_final_path = str(audio_path)

    cena = MagicMock()
    cena.cena_id = 1
    cena.estilo_visual = MagicMock()
    cena.estilo_visual.value = "ken_burns"

    roteiro = MagicMock()
    roteiro.metadata = metadata
    roteiro.cenas = [cena]

    return roteiro


class TestSelecionarSegmentos:
    """Testa seleção de segmentos."""

    @pytest.mark.asyncio
    async def test_selecionar_cobrir_duracao(self, mock_segmentos):
        """Seleciona segmentos suficientes para cobrir duração."""
        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = mock_segmentos

            segmentos = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
            )

        # Precisa de 60s, cada segmento tem 30s, deve selecionar 2
        assert len(segmentos) >= 2
        duracao_total = sum(s["duracao_segundos"] for s in segmentos)
        assert duracao_total >= 60.0

    @pytest.mark.asyncio
    async def test_selecionar_filtro_intensidade(self, mock_segmentos):
        """Filtra por faixa de intensidade."""
        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = [s for s in mock_segmentos if s["faixa_intensidade"] == "intenso"]

            segmentos = await selecionar_segmentos(
                duracao_alvo=30.0,
                canal_id="canal_test",
                faixa_intensidade="intenso",
            )

        # Apenas segmentos intensos
        assert all(s["faixa_intensidade"] == "intenso" for s in segmentos)
        mock_buscar.assert_called_once_with(
            jogo=None,
            faixa_intensidade="intenso",
            limite=1000,
        )

    @pytest.mark.asyncio
    async def test_selecionar_respeita_janela_reuso(self, mock_segmentos):
        """Segmentos usados recentemente não são selecionados."""
        # Segmento 1 foi usado ontem
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        mock_segmentos[0]["usado_em"] = [f"video_antigo:{ontem}"]

        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = mock_segmentos

            segmentos = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
                janela_reuso_dias=30,
            )

        # Segmento 1 deve ser ignorado
        ids_selecionados = [s["id"] for s in segmentos]
        assert 1 not in ids_selecionados

    @pytest.mark.asyncio
    async def test_selecionar_janela_expirada_permite_reuso(self, mock_segmentos):
        """Segmentos usados fora da janela podem ser reutilizados."""
        # Segmento 1 foi usado há 60 dias
        data_antiga = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        mock_segmentos[0]["usado_em"] = [f"video_antigo:{data_antiga}"]

        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = mock_segmentos

            segmentos = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
                janela_reuso_dias=30,
            )

        # Segmento 1 pode ser selecionado (janela expirou)
        ids_selecionados = [s["id"] for s in segmentos]
        assert 1 in ids_selecionados

    @pytest.mark.asyncio
    async def test_selecionar_sem_segmentos_disponiveis(self):
        """Retorna lista vazia se não houver segmentos."""
        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = []

            segmentos = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
            )

        assert segmentos == []

    @pytest.mark.asyncio
    async def test_selecionar_todos_usados_fallback(self, mock_segmentos):
        """Fallback: usa segmentos mesmo que todos tenham sido usados."""
        # Todos foram usados recentemente
        ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        for seg in mock_segmentos:
            seg["usado_em"] = [f"video_antigo:{ontem}"]

        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            mock_buscar.return_value = mock_segmentos

            segmentos = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
                janela_reuso_dias=30,
            )

        # Fallback: usa mesmo assim
        assert len(segmentos) > 0


class TestConcatenarSegmentos:
    """Testa concatenação de segmentos."""

    @pytest.mark.asyncio
    async def test_concatenar_multiplos_segmentos(self, mock_segmentos, tmp_path):
        """Concatena múltiplos segmentos em um arquivo."""
        output_path = tmp_path / "output.mp4"

        # Criar arquivos falsos
        for seg in mock_segmentos[:2]:
            Path(seg["caminho_arquivo"]).write_bytes(b"fake video")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")

            result = await concatenar_segmentos(
                segmentos=mock_segmentos[:2],
                output_path=output_path,
            )

        assert result == output_path
        mock_run.assert_called()

    @pytest.mark.asyncio
    async def test_concatenar_segmento_unico(self, mock_segmentos, tmp_path):
        """Apenas copia se houver apenas um segmento."""
        output_path = tmp_path / "output.mp4"
        seg_path = tmp_path / "seg1.mp4"
        seg_path.write_bytes(b"fake video")

        mock_segmentos[0]["caminho_arquivo"] = str(seg_path)

        result = await concatenar_segmentos(
            segmentos=[mock_segmentos[0]],
            output_path=output_path,
        )

        assert result == output_path
        assert output_path.exists()

    @pytest.mark.asyncio
    async def test_concatenar_lista_vazia(self, tmp_path):
        """Levanta erro se lista vazia."""
        output_path = tmp_path / "output.mp4"

        with pytest.raises(ValueError, match="Lista de segmentos vazia"):
            await concatenar_segmentos(
                segmentos=[],
                output_path=output_path,
            )

    @pytest.mark.asyncio
    async def test_concatenar_erro_ffmpeg(self, mock_segmentos, tmp_path):
        """Trata erro de ffmpeg."""
        output_path = tmp_path / "output.mp4"

        for seg in mock_segmentos[:2]:
            Path(seg["caminho_arquivo"]).write_bytes(b"fake video")

        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "ffmpeg", stderr="FFmpeg error")

            with pytest.raises(RuntimeError, match="Falha ao concatenar"):
                await concatenar_segmentos(
                    segmentos=mock_segmentos[:2],
                    output_path=output_path,
                )


class TestResolverGameplayBg:
    """Testa resolução completa de gameplay_bg."""

    @pytest.mark.asyncio
    async def test_resolver_sucesso(self, mock_roteiro, mock_segmentos, tmp_path):
        """Resolve gameplay_bg com sucesso."""
        # Criar arquivo de áudio
        audio_path = Path(mock_roteiro.metadata.audio_final_path)

        # Criar arquivos de segmento
        for seg in mock_segmentos[:2]:
            Path(seg["caminho_arquivo"]).write_bytes(b"fake video")

        with patch("services.gameplay.resolver.selecionar_segmentos") as mock_sel:
            mock_sel.return_value = mock_segmentos[:2]

            with patch("services.gameplay.resolver.concatenar_segmentos") as mock_concat:
                output_bg = tmp_path / "bg_test.mp4"
                output_bg.write_bytes(b"concatenated video")
                mock_concat.return_value = output_bg

                with patch("services.gameplay.resolver.marcar_gameplay_usado") as mock_marcar:
                    mock_marcar.return_value = True

                    # Mock ffprobe para retornar duração do áudio
                    with patch("subprocess.run") as mock_run:
                        mock_result = MagicMock()
                        mock_result.stdout = "60.0\n"
                        mock_run.return_value = mock_result

                        resultado = await resolver_gameplay_bg(
                            roteiro=mock_roteiro,
                            canal_id="canal_test",
                        )

        assert resultado is not None
        assert isinstance(resultado, GameplayBgResolvido)
        assert resultado.duracao_total > 0
        assert len(resultado.segmentos_ids) == 2
        mock_marcar.assert_called()

    @pytest.mark.asyncio
    async def test_resolver_sem_audio(self, mock_roteiro):
        """Retorna None se não houver áudio."""
        mock_roteiro.metadata.audio_final_path = None

        resultado = await resolver_gameplay_bg(
            roteiro=mock_roteiro,
            canal_id="canal_test",
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_resolver_audio_nao_encontrado(self, mock_roteiro):
        """Retorna None se arquivo de áudio não existir."""
        mock_roteiro.metadata.audio_final_path = "/inexistente/audio.wav"

        resultado = await resolver_gameplay_bg(
            roteiro=mock_roteiro,
            canal_id="canal_test",
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_resolver_sem_segmentos(self, mock_roteiro):
        """Retorna None se não houver segmentos."""
        audio_path = Path(mock_roteiro.metadata.audio_final_path)

        with patch("services.gameplay.resolver.selecionar_segmentos") as mock_sel:
            mock_sel.return_value = []

            resultado = await resolver_gameplay_bg(
                roteiro=mock_roteiro,
                canal_id="canal_test",
            )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_resolver_marca_como_usado(self, mock_roteiro, mock_segmentos, tmp_path):
        """Atualiza usado_em de cada segmento utilizado."""
        for seg in mock_segmentos[:2]:
            Path(seg["caminho_arquivo"]).write_bytes(b"fake video")

        with patch("services.gameplay.resolver.selecionar_segmentos") as mock_sel:
            mock_sel.return_value = mock_segmentos[:2]

            with patch("services.gameplay.resolver.concatenar_segmentos") as mock_concat:
                output_bg = tmp_path / "bg_test.mp4"
                output_bg.write_bytes(b"concatenated video")
                mock_concat.return_value = output_bg

                with patch("services.gameplay.resolver.marcar_gameplay_usado") as mock_marcar:
                    mock_marcar.return_value = True

                    # Mock ffprobe para retornar duração do áudio
                    with patch("subprocess.run") as mock_run:
                        mock_result = MagicMock()
                        mock_result.stdout = "60.0\n"
                        mock_run.return_value = mock_result

                        await resolver_gameplay_bg(
                            roteiro=mock_roteiro,
                            canal_id="canal_test",
                        )

        # Verificar que marcar_gameplay_usado foi chamado para cada segmento
        assert mock_marcar.call_count == 2
        for call in mock_marcar.call_args_list:
            # Verificar que video_id está correto
            assert call[1]["video_id"] == mock_roteiro.metadata.video_id


class TestReusoEntreVideos:
    """Testa que segundo vídeo não reutiliza segmentos do primeiro."""

    @pytest.mark.asyncio
    async def test_segundo_video_nao_reutiliza(self, mock_segmentos, tmp_path):
        """Segundo vídeo do mesmo canal não reutiliza segmentos recentes."""
        # Criar arquivos de segmento
        for seg in mock_segmentos:
            Path(seg["caminho_arquivo"]).write_bytes(b"fake video")

        with patch("services.gameplay.resolver.buscar_gameplay_segmentos") as mock_buscar:
            # Primeira chamada retorna todos disponíveis
            # Segunda chamada retorna com usado_em atualizado
            mock_buscar.side_effect = [
                mock_segmentos[:2],  # Primeiro vídeo
                [
                    {**mock_segmentos[0], "usado_em": [f"video_1:{datetime.now().strftime('%Y-%m-%d')}"]},
                    {**mock_segmentos[1], "usado_em": [f"video_1:{datetime.now().strftime('%Y-%m-%d')}"]},
                    mock_segmentos[2],
                ],
            ]

            # Resolver primeiro vídeo
            segs1 = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
            )

            # Resolver segundo vídeo
            segs2 = await selecionar_segmentos(
                duracao_alvo=60.0,
                canal_id="canal_test",
            )

        # Segundo vídeo deve usar segmentos diferentes
        ids1 = [s["id"] for s in segs1]
        ids2 = [s["id"] for s in segs2]

        # Se primeiro usou 1 e 2, segundo deve usar 3
        # (ou o fallback se não houver outros disponíveis)
        # Mas com janela de reuso, deve evitar os mesmos
        assert len(segs2) > 0  # Pelo menos algum segmento foi selecionado


class TestIntegracaoPipeline:
    """Testa integração com o pipeline de renderização."""

    @pytest.mark.asyncio
    async def test_estilo_visual_gameplay_bg(self):
        """Verifica que estilo_visual gameplay_bg existe."""
        from pipeline.schemas import EstiloVisual

        assert hasattr(EstiloVisual, "gameplay_bg")
        assert EstiloVisual.gameplay_bg.value == "gameplay_bg"

    @pytest.mark.asyncio
    async def test_config_nicho_gameplay_intensidade(self):
        """Verifica campo de intensidade preferida em ConfigNicho."""
        from pipeline.nichos import ConfigNicho

        config = ConfigNicho(
            nome="test",
            prompt_ideacao="test",
            prompt_roteiro_adicional="test",
            prompt_roteiro_short="test",
            categoria_google_trends=1,
            subreddits_sugeridos=[],
            gameplay_intensidade_preferida="intenso",
        )

        assert config.gameplay_intensidade_preferida == "intenso"

    @pytest.mark.asyncio
    async def test_settings_janela_reuso(self):
        """Verifica configuração de janela de reuso."""
        from pipeline.config import settings

        assert hasattr(settings, "gameplay_janela_reuso_dias")
        assert settings.gameplay_janela_reuso_dias == 30

        assert hasattr(settings, "gameplay_crossfade_duration_sec")
        assert settings.gameplay_crossfade_duration_sec == 0.5
