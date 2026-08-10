"""Testes do pipeline de áudio (Fase 3)."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, patch
import tempfile

from pipeline.schemas import (
    Cena, Palavra, Midia, EfeitosVisuais, Overlays,
    TipoAsset, AnimacaoImagem,
)
from services.audio.validator import _calcular_wer, _normalizar_texto
from services.audio.mixer import _ajustar_timestamps_absolutos


def _criar_cena_minima(cena_id: int, texto: str, **kwargs) -> Cena:
    """Helper para criar Cena com campos obrigatórios."""
    return Cena(
        cena_id=cena_id,
        ordem=cena_id,
        texto_locucao=texto,
        duracao_estimada_segundos=5.0,
        midia=Midia(
            tipo_asset_preferencial=TipoAsset.imagem,
            keywords_busca=["teste"],
            fallback_query="teste",
            duracao_minima=5.0,
        ),
        efeitos_visuais=EfeitosVisuais(
            animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
        ),
        overlays=Overlays(),
        **kwargs,
    )


class TestCalculoWER:
    """Testes do cálculo de Word Error Rate."""

    def test_wer_textos_identicos(self):
        """WER = 0 quando textos são idênticos."""
        ref = "O Naruto é um ninja muito poderoso"
        hip = "O Naruto é um ninja muito poderoso"
        wer = _calcular_wer(ref, hip)
        assert wer == 0.0

    def test_wer_uma_palavra_trocada(self):
        """WER > 0 com uma palavra diferente."""
        ref = "O Naruto é um ninja muito poderoso"
        hip = "O Naruto é um ninja muito forte"
        wer = _calcular_wer(ref, hip)
        # 1 substituição em 7 palavras = 1/7 ≈ 0.143
        assert 0.1 < wer < 0.2

    def test_wer_palavra_extra(self):
        """WER com inserção de palavra."""
        ref = "O Naruto é um ninja"
        hip = "O Naruto é um grande ninja"
        # 1 inserção em 5 palavras = 1/5 = 0.2
        wer = _calcular_wer(ref, hip)
        assert 0.15 < wer < 0.25

    def test_wer_palavra_faltando(self):
        """WER com deleção de palavra."""
        ref = "O Naruto é um ninja muito poderoso"
        hip = "O Naruto é um ninja poderoso"
        # 1 deleção em 7 palavras = 1/7 ≈ 0.143
        wer = _calcular_wer(ref, hip)
        assert 0.1 < wer < 0.2

    def test_wer_case_insensitive(self):
        """WER ignora diferenças de case."""
        ref = "O Naruto é um NINJA muito poderoso"
        hip = "o naruto é um ninja muito poderoso"
        wer = _calcular_wer(ref, hip)
        assert wer == 0.0

    def test_wer_ignora_pontuacao(self):
        """WER ignora pontuação."""
        ref = "O Naruto é um ninja, muito poderoso!"
        hip = "O Naruto é um ninja muito poderoso"
        wer = _calcular_wer(ref, hip)
        assert wer == 0.0

    def test_wer_multiplos_erros(self):
        """WER com múltiplos erros."""
        ref = "O Sasuke é o último Uchiha vivo"
        hip = "O Sasuke foi o primeiro Uchiha"
        # Substituições e deleções
        wer = _calcular_wer(ref, hip)
        assert wer > 0.3

    def test_texto_vazio(self):
        """WER com texto vazio."""
        wer = _calcular_wer("", "")
        assert wer == 0.0

    def test_referencia_vazia_com_hipotese(self):
        """WER com referência vazia e hipótese não vazia."""
        wer = _calcular_wer("", "texto")
        assert wer == 1.0


class TestNormalizacaoTexto:
    """Testes da normalização de texto para WER."""

    def test_minusculas(self):
        """Converte para minúsculas."""
        resultado = _normalizar_texto("NARUTO Uchiha")
        assert resultado == "naruto uchiha"

    def test_remove_pontuacao(self):
        """Remove pontuação."""
        resultado = _normalizar_texto("O Naruto, é um ninja! Poderoso?")
        assert resultado == "o naruto é um ninja poderoso"

    def test_normaliza_espacos(self):
        """Normaliza espaços múltiplos."""
        resultado = _normalizar_texto("O   Naruto    é    ninja")
        assert resultado == "o naruto é ninja"

    def test_mantem_numeros(self):
        """Mantém números."""
        resultado = _normalizar_texto("Tem 7 ninjas na vila")
        assert "7" in resultado


class TestTimestampsAbsolutos:
    """Testes do ajuste de timestamps absolutos."""

    def test_timestamps_simples(self):
        """Ajusta timestamps de uma única cena."""
        cena = _criar_cena_minima(
            cena_id=1,
            texto="Teste",
            audio_path="/tmp/test.wav",
            palavras_transcritas=[
                Palavra(text="teste", start=0.0, end=0.5),
                Palavra(text="audio", start=0.6, end=1.2),
            ],
        )

        palavras = _ajustar_timestamps_absolutos([cena])

        assert len(palavras) == 2
        # Primeira palavra não deve ter offset
        assert palavras[0].start == 0.0
        assert palavras[0].end == 0.5
        assert palavras[1].start == 0.6
        assert palavras[1].end == 1.2

    def test_timestamps_multiplas_cenas(self):
        """Ajusta timestamps com offset acumulado."""
        cena1 = _criar_cena_minima(
            cena_id=1,
            texto="Primeira cena",
            audio_path="/tmp/test1.wav",
            palavras_transcritas=[
                Palavra(text="primeira", start=0.0, end=0.5),
                Palavra(text="cena", start=0.6, end=1.0),
            ],
        )

        cena2 = _criar_cena_minima(
            cena_id=2,
            texto="Segunda cena",
            audio_path="/tmp/test2.wav",
            palavras_transcritas=[
                Palavra(text="segunda", start=0.0, end=0.6),
                Palavra(text="cena", start=0.7, end=1.2),
            ],
        )

        palavras = _ajustar_timestamps_absolutos([cena1, cena2])

        assert len(palavras) == 4
        # Primeira cena: sem offset
        assert palavras[0].start == 0.0
        assert palavras[1].end == 1.0
        # Segunda cena: offset de 1.0 (duração da primeira cena baseada na última palavra)
        assert palavras[2].start == 1.0  # 0.0 + 1.0
        assert palavras[2].end == 1.6   # 0.6 + 1.0
        assert palavras[3].start == 1.7  # 0.7 + 1.0
        assert palavras[3].end == 2.2   # 1.2 + 1.0

    def test_cena_sem_palavras(self):
        """Lida com cena sem palavras transcritas."""
        cena = _criar_cena_minima(
            cena_id=1,
            texto="Teste",
            audio_path="/tmp/test.wav",
            palavras_transcritas=None,
        )

        palavras = _ajustar_timestamps_absolutos([cena])
        assert palavras == []


class TestRetrySeed:
    """Testes do loop de retry com seed."""

    @pytest.mark.asyncio
    async def test_sucesso_primeira_tentativa(self):
        """Sucesso na primeira tentativa sem retry."""
        from services.audio.pipeline_audio import gerar_e_validar_cena

        cena = _criar_cena_minima(
            cena_id=1,
            texto="O Naruto é um ninja poderoso",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("services.audio.pipeline_audio.gerar_audio_cena", new_callable=AsyncMock) as mock_tts:
                with patch("services.audio.pipeline_audio.validar_audio", new_callable=AsyncMock) as mock_valid:
                    mock_tts.return_value = Path(f"{tmpdir}/cena_001.wav")
                    mock_valid.return_value = (0.02, [Palavra(text="teste", start=0.0, end=0.5)])

                    audio, wer, palavras = await gerar_e_validar_cena(cena, Path(tmpdir))

                    assert mock_tts.call_count == 1
                    assert wer == 0.02
                    assert cena.revisao_manual_necessaria is False

    @pytest.mark.asyncio
    async def test_sucesso_apos_retry(self):
        """Sucesso após retry com seed diferente."""
        from services.audio.pipeline_audio import gerar_e_validar_cena

        cena = _criar_cena_minima(
            cena_id=1,
            texto="O Naruto é um ninja poderoso",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("services.audio.pipeline_audio.gerar_audio_cena", new_callable=AsyncMock) as mock_tts:
                with patch("services.audio.pipeline_audio.validar_audio", new_callable=AsyncMock) as mock_valid:
                    mock_tts.return_value = Path(f"{tmpdir}/cena_001.wav")
                    # Primeira tentativa: WER alto, segunda: WER baixo
                    mock_valid.side_effect = [
                        (0.20, [Palavra(text="teste", start=0.0, end=0.5)]),  # WER alto (> 0.15)
                        (0.03, [Palavra(text="teste", start=0.0, end=0.5)]),  # WER baixo
                    ]

                    audio, wer, palavras = await gerar_e_validar_cena(cena, Path(tmpdir), max_tentativas=3)

                    assert mock_tts.call_count == 2  # Dois attempts
                    assert wer == 0.03
                    assert cena.revisao_manual_necessaria is False

    @pytest.mark.asyncio
    async def test_esgotamento_tentativas(self):
        """Marca revisao_manual_necessaria ao esgotar tentativas."""
        from services.audio.pipeline_audio import gerar_e_validar_cena

        cena = _criar_cena_minima(
            cena_id=1,
            texto="O Naruto é um ninja poderoso",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("services.audio.pipeline_audio.gerar_audio_cena", new_callable=AsyncMock) as mock_tts:
                with patch("services.audio.pipeline_audio.validar_audio", new_callable=AsyncMock) as mock_valid:
                    mock_tts.return_value = Path(f"{tmpdir}/cena_001.wav")
                    # Todas tentativas com WER alto
                    mock_valid.return_value = (0.20, [Palavra(text="teste", start=0.0, end=0.5)])

                    audio, wer, palavras = await gerar_e_validar_cena(cena, Path(tmpdir), max_tentativas=3)

                    assert mock_tts.call_count == 3
                    assert cena.revisao_manual_necessaria is True
                    assert cena.wer_final == 0.20
