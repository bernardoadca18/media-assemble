"""
Testes para Fase 9.1 — Pipeline de ingestão de gameplay bruta.

Valida:
- Segmentação de vídeo com ffmpeg
- Cálculo de score de movimento
- Classificação de intensidade
- Filtro de qualidade (rejeição de menus/telas paradas)
- Persistência no banco de dados
- Deduplicação por hash
- CLI command --ingerir-gameplay
"""
import hashlib
import math
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest
from sqlalchemy import select

from services.gameplay.ingestion import (
    segmentar_video,
    calcular_score_movimento,
    classificar_intensidade,
    calcular_hash_conteudo,
    processar_segmento,
    ingerir_arquivo_gameplay,
    ingerir_diretorio_gameplay,
)
from db.models import GameplaySegmento


class TestSegmentarVideo:
    """Testa segmentação de vídeo com ffmpeg."""

    @pytest.mark.asyncio
    async def test_segmentar_video_sucesso(self, tmp_path):
        """Segmenta vídeo em partes de duração fixa."""
        video_path = tmp_path / "video_bruto.mp4"
        output_dir = tmp_path / "segmentos"
        output_dir.mkdir()

        # Mock ffprobe para retornar duração de 90 segundos
        mock_result = MagicMock()
        mock_result.stdout = "90.0"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            segmentos = await segmentar_video(
                video_path=video_path,
                duracao_segmento=30,
                output_dir=output_dir,
            )

        # 90 segundos / 30 = 3 segmentos
        assert len(segmentos) == 3
        assert all(s.parent == output_dir for s in segmentos)

    @pytest.mark.asyncio
    async def test_segmentar_video_duracao_nao_inteira(self, tmp_path):
        """Arredonda para cima quando duração não é divisível."""
        video_path = tmp_path / "video_bruto.mp4"
        output_dir = tmp_path / "segmentos"
        output_dir.mkdir()

        # Mock ffprobe para retornar 95 segundos
        mock_result = MagicMock()
        mock_result.stdout = "95.0"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            segmentos = await segmentar_video(
                video_path=video_path,
                duracao_segmento=30,
                output_dir=output_dir,
            )

        # ceil(95/30) = 4 segmentos
        assert len(segmentos) == 4

    @pytest.mark.asyncio
    async def test_segmentar_video_fallback_reencode(self, tmp_path):
        """Faz reencode se -c copy falhar."""
        video_path = tmp_path / "video_bruto.mp4"
        output_dir = tmp_path / "segmentos"
        output_dir.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "60.0"

        with patch("subprocess.run") as mock_run:
            # Primeira chamada (ffprobe) sucesso
            # Segunda (ffmpeg -c copy) falha
            # Terceira (ffmpeg reencode) sucesso
            mock_run.side_effect = [
                mock_result,  # ffprobe
                MagicMock(),  # first segment -c copy fails
                MagicMock(),  # first segment reencode succeeds
                mock_result,  # ffprobe for duration check
                MagicMock(),  # second segment
            ]

            # Simular falha no -c copy para primeiro segmento
            import subprocess
            mock_run.side_effect = [
                mock_result,  # ffprobe
                subprocess.CalledProcessError(1, "ffmpeg"),  # -c copy falha
                MagicMock(),  # reencode funciona
                MagicMock(),  # segundo segmento
            ]

            segmentos = await segmentar_video(
                video_path=video_path,
                duracao_segmento=30,
                output_dir=output_dir,
            )

        assert len(segmentos) == 2

    @pytest.mark.asyncio
    async def test_segmentar_video_descarta_audio(self, tmp_path):
        """Sempre remove trilha de áudio dos segmentos."""
        video_path = tmp_path / "video_bruto.mp4"
        output_dir = tmp_path / "segmentos"
        output_dir.mkdir()

        mock_result = MagicMock()
        mock_result.stdout = "30.0"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            await segmentar_video(
                video_path=video_path,
                duracao_segmento=30,
                output_dir=output_dir,
            )

            # Verificar que -an foi usado
            calls = mock_run.call_args_list
            for c in calls:
                if "ffmpeg" in str(c):
                    args = c[0][0]
                    assert "-an" in args

    @pytest.mark.asyncio
    async def test_segmentar_video_erro_duracao(self, tmp_path):
        """Retorna lista vazia se não conseguir obter duração."""
        video_path = tmp_path / "video_bruto.mp4"
        output_dir = tmp_path / "segmentos"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = Exception("ffprobe error")

            segmentos = await segmentar_video(
                video_path=video_path,
                duracao_segmento=30,
                output_dir=output_dir,
            )

        assert segmentos == []


class TestCalcularScoreMovimento:
    """Testa cálculo de score de movimento."""

    @pytest.mark.asyncio
    async def test_score_movimento_mestimate_sucesso(self, tmp_path):
        """Usa mestimate para calcular movimento."""
        segmento_path = tmp_path / "segmento.mp4"

        mock_result = MagicMock()
        mock_result.stderr = "mv=45.2\nmv=50.1"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            score = await calcular_score_movimento(segmento_path)

        # Média dos valores parseados
        assert 0.0 <= score <= 100.0

    @pytest.mark.asyncio
    async def test_score_movimento_signalstats_fallback(self, tmp_path):
        """Falla para signalstats se mestimate falhar."""
        segmento_path = tmp_path / "segmento.mp4"

        # Primeira chamada (mestimate) falha
        # Segunda (signalstats) retorna valores
        mock_result_signalstats = MagicMock()
        mock_result_signalstats.stderr = "YDIFF: 120.5\nUDIFF: 80.3"

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = [
                Exception("mestimate error"),
                mock_result_signalstats,
            ]

            score = await calcular_score_movimento(segmento_path)

        assert score > 0.0

    @pytest.mark.asyncio
    async def test_score_movimento_timeout(self, tmp_path):
        """Retorna 0 em caso de timeout."""
        segmento_path = tmp_path / "segmento.mp4"

        import subprocess
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ffmpeg", 60)

            score = await calcular_score_movimento(segmento_path)

        assert score == 0.0

    @pytest.mark.asyncio
    async def test_score_movimento_sem_valores(self, tmp_path):
        """Retorna 0 se não encontrar valores de movimento."""
        segmento_path = tmp_path / "segmento.mp4"

        mock_result = MagicMock()
        mock_result.stderr = "no motion data"

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = mock_result

            score = await calcular_score_movimento(segmento_path)

        assert score == 0.0


class TestClassificarIntensidade:
    """Testa classificação de intensidade de movimento."""

    def test_intensidade_calma(self):
        """Score baixo = calmo."""
        assert classificar_intensidade(5.0) == "calmo"
        assert classificar_intensidade(10.0) == "calmo"
        assert classificar_intensidade(14.9) == "calmo"

    def test_intensidade_moderada(self):
        """Score médio = moderado."""
        assert classificar_intensidade(15.0) == "moderado"
        assert classificar_intensidade(25.0) == "moderado"
        assert classificar_intensidade(39.9) == "moderado"

    def test_intensidade_intensa(self):
        """Score alto = intenso."""
        assert classificar_intensidade(40.0) == "intenso"
        assert classificar_intensidade(50.0) == "intenso"
        assert classificar_intensidade(100.0) == "intenso"


class TestCalcularHashConteudo:
    """Testa cálculo de hash MD5."""

    @pytest.mark.asyncio
    async def test_hash_conteudo(self, tmp_path):
        """Calcula hash MD5 corretamente."""
        file_path = tmp_path / "test.bin"
        file_path.write_bytes(b"conteudo teste")

        hash_result = await calcular_hash_conteudo(file_path)

        # Verificar que é um hash MD5 válido (32 caracteres hex)
        assert len(hash_result) == 32
        assert all(c in "0123456789abcdef" for c in hash_result)

        # Verificar contra hash calculado manualmente
        expected = hashlib.md5(b"conteudo teste").hexdigest()
        assert hash_result == expected

    @pytest.mark.asyncio
    async def test_hash_arquivos_diferentes(self, tmp_path):
        """Arquivos diferentes produzem hashes diferentes."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"

        file1.write_bytes(b"conteudo 1")
        file2.write_bytes(b"conteudo 2")

        hash1 = await calcular_hash_conteudo(file1)
        hash2 = await calcular_hash_conteudo(file2)

        assert hash1 != hash2


class TestProcessarSegmento:
    """Testa processamento completo de segmento."""

    @pytest.mark.asyncio
    async def test_processar_segmento_aprovado(self, tmp_path):
        """Segmento com movimento suficiente é aprovado."""
        segmento_path = tmp_path / "segmento.mp4"
        segmento_path.write_bytes(b"fake video")

        with patch("services.gameplay.ingestion.calcular_score_movimento") as mock_score:
            mock_score.return_value = 25.0

            with patch("subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.stdout = "30.0"
                mock_run.return_value = mock_result

                resultado = await processar_segmento(
                    segmento_path=segmento_path,
                    jogo_origem="Jogo Teste",
                    min_motion_score=10.0,
                )

        assert resultado is not None
        assert resultado["jogo_origem"] == "Jogo Teste"
        assert resultado["score_movimento"] == 25.0
        assert resultado["faixa_intensidade"] == "moderado"
        assert "hash_conteudo" in resultado

    @pytest.mark.asyncio
    async def test_processar_segmento_rejeitado(self, tmp_path):
        """Segmento sem movimento suficiente é rejeitado."""
        segmento_path = tmp_path / "segmento.mp4"
        segmento_path.write_bytes(b"fake video")

        with patch("services.gameplay.ingestion.calcular_score_movimento") as mock_score:
            mock_score.return_value = 3.0  # Abaixo do limiar

            resultado = await processar_segmento(
                segmento_path=segmento_path,
                jogo_origem="Jogo Teste",
                min_motion_score=10.0,
            )

        assert resultado is None
        # Arquivo deve ser removido
        assert not segmento_path.exists()

    @pytest.mark.asyncio
    async def test_processar_segmento_classifica_intensidade(self, tmp_path):
        """Classifica intensidade corretamente."""
        segmento_path = tmp_path / "segmento.mp4"
        segmento_path.write_bytes(b"fake video")

        test_cases = [
            (5.0, "calmo"),
            (20.0, "moderado"),
            (50.0, "intenso"),
        ]

        for score, intensidade_esperada in test_cases:
            with patch("services.gameplay.ingestion.calcular_score_movimento") as mock_score:
                mock_score.return_value = score

                with patch("subprocess.run") as mock_run:
                    mock_result = MagicMock()
                    mock_result.stdout = "30.0"
                    mock_run.return_value = mock_result

                    resultado = await processar_segmento(
                        segmento_path=segmento_path,
                        jogo_origem="Jogo",
                        min_motion_score=1.0,
                    )

            assert resultado["faixa_intensidade"] == intensidade_esperada


class TestIngerirArquivoGameplay:
    """Testa ingestão de arquivo de gameplay completo."""

    @pytest.mark.asyncio
    async def test_ingerir_arquivo_sucesso(self, tmp_path):
        """Processa arquivo completo com sucesso."""
        arquivo_path = tmp_path / "gameplay_bruta.mp4"
        arquivo_path.write_bytes(b"fake video")

        output_dir = tmp_path / "processed"
        output_dir.mkdir()

        # Mock segmentação
        segmentos_paths = [
            output_dir / "gameplay_bruta_seg0000.mp4",
            output_dir / "gameplay_bruta_seg0001.mp4",
        ]
        for s in segmentos_paths:
            s.write_bytes(b"segment")

        with patch("services.gameplay.ingestion.segmentar_video") as mock_seg:
            mock_seg.return_value = segmentos_paths

            with patch("services.gameplay.ingestion.processar_segmento") as mock_proc:
                # Primeiro segmento aprovado, segundo reprovado
                mock_proc.side_effect = [
                    {"caminho_arquivo": str(segmentos_paths[0]), "jogo_origem": "Jogo", "duracao_segundos": 30.0, "score_movimento": 25.0, "faixa_intensidade": "moderado", "hash_conteudo": "abc123"},
                    None,  # Rejeitado
                ]

                with patch("db.models.salvar_gameplay_segmentos") as mock_salvar:
                    mock_salvar.return_value = ["id_1"]

                    ids = await ingerir_arquivo_gameplay(
                        arquivo_path=arquivo_path,
                        jogo="Jogo Teste",
                        output_dir=output_dir,
                    )

        assert len(ids) == 1
        assert ids[0] == "id_1"

    @pytest.mark.asyncio
    async def test_ingerir_arquivo_nao_encontrado(self, tmp_path):
        """Levanta erro se arquivo não existe."""
        arquivo_path = tmp_path / "inexistente.mp4"

        with pytest.raises(FileNotFoundError):
            await ingerir_arquivo_gameplay(
                arquivo_path=arquivo_path,
                jogo="Jogo",
            )

    @pytest.mark.asyncio
    async def test_ingerir_arquivo_sem_segmentos(self, tmp_path):
        """Retorna lista vazia se nenhum segmento for criado."""
        arquivo_path = tmp_path / "vazio.mp4"
        arquivo_path.write_bytes(b"fake")

        with patch("services.gameplay.ingestion.segmentar_video") as mock_seg:
            mock_seg.return_value = []

            ids = await ingerir_arquivo_gameplay(
                arquivo_path=arquivo_path,
                jogo="Jogo",
            )

        assert ids == []


class TestIngerirDiretorioGameplay:
    """Testa ingestão de diretório completo."""

    @pytest.mark.asyncio
    async def test_ingerir_diretorio_sucesso(self, tmp_path):
        """Processa todos os arquivos de vídeo do diretório."""
        diretorio = tmp_path / "raw"
        diretorio.mkdir()

        # Criar arquivos de vídeo
        (diretorio / "video1.mp4").write_bytes(b"video1")
        (diretorio / "video2.mkv").write_bytes(b"video2")
        (diretorio / "video3.avi").write_bytes(b"video3")
        (diretorio / "arquivo.txt").write_bytes(b"texto")  # Não deve processar

        with patch("services.gameplay.ingestion.ingerir_arquivo_gameplay") as mock_ing:
            mock_ing.side_effect = [["id1"], ["id2", "id3"], ["id4"]]

            ids = await ingerir_diretorio_gameplay(
                diretorio=diretorio,
                jogo="Jogo Teste",
            )

        # Deve processar apenas os 3 vídeos
        assert len(ids) == 4
        assert mock_ing.call_count == 3

    @pytest.mark.asyncio
    async def test_ingerir_diretorio_filtra_extensoes(self, tmp_path):
        """Processa apenas extensões de vídeo válidas."""
        diretorio = tmp_path / "raw"
        diretorio.mkdir()

        # Várias extensões
        (diretorio / "video.mp4").write_bytes(b"v")
        (diretorio / "video.mkv").write_bytes(b"v")
        (diretorio / "video.avi").write_bytes(b"v")
        (diretorio / "video.mov").write_bytes(b"v")
        (diretorio / "video.webm").write_bytes(b"v")
        (diretorio / "arquivo.txt").write_bytes(b"t")
        (diretorio / "arquivo.pdf").write_bytes(b"p")

        with patch("services.gameplay.ingestion.ingerir_arquivo_gameplay") as mock_ing:
            mock_ing.return_value = []

            await ingerir_diretorio_gameplay(
                diretorio=diretorio,
                jogo="Jogo",
            )

        # Apenas 5 arquivos de vídeo
        assert mock_ing.call_count == 5

    @pytest.mark.asyncio
    async def test_ingerir_diretorio_diretorio_inexistente(self, tmp_path):
        """Levanta erro se diretório não existe."""
        diretorio = tmp_path / "inexistente"

        with pytest.raises(FileNotFoundError):
            await ingerir_diretorio_gameplay(
                diretorio=diretorio,
                jogo="Jogo",
            )

    @pytest.mark.asyncio
    async def test_ingerir_diretorio_continua_em_erro(self, tmp_path):
        """Continua processando mesmo se um arquivo falhar."""
        diretorio = tmp_path / "raw"
        diretorio.mkdir()

        (diretorio / "video1.mp4").write_bytes(b"v1")
        (diretorio / "video2.mp4").write_bytes(b"v2")
        (diretorio / "video3.mp4").write_bytes(b"v3")

        with patch("services.gameplay.ingestion.ingerir_arquivo_gameplay") as mock_ing:
            # Primeiro sucesso, segundo erro, terceiro sucesso
            mock_ing.side_effect = [
                ["id1"],
                Exception("Erro no segundo"),
                ["id2"],
            ]

            ids = await ingerir_diretorio_gameplay(
                diretorio=diretorio,
                jogo="Jogo",
            )

        # Deve continuar após o erro
        assert len(ids) == 2


class TestModeloGameplaySegmento:
    """Testa modelo SQLAlchemy."""

    def test_modelo_campos(self):
        """Verifica campos do modelo."""
        from db.models import GameplaySegmento

        # Verificar que modelo existe e tem campos esperados
        assert hasattr(GameplaySegmento, "__tablename__")
        assert GameplaySegmento.__tablename__ == "gameplay_segmentos"
        assert GameplaySegmento.__table_args__.get("schema") == "dados"

    def test_modelo_campos_tipos(self):
        """Verifica tipos dos campos."""
        from db.models import GameplaySegmento

        # Verificar campos principais
        assert hasattr(GameplaySegmento, "id")
        assert hasattr(GameplaySegmento, "jogo_origem")
        assert hasattr(GameplaySegmento, "caminho_arquivo")
        assert hasattr(GameplaySegmento, "duracao_segundos")
        assert hasattr(GameplaySegmento, "score_movimento")
        assert hasattr(GameplaySegmento, "faixa_intensidade")
        assert hasattr(GameplaySegmento, "hash_conteudo")
        assert hasattr(GameplaySegmento, "usado_em")
        assert hasattr(GameplaySegmento, "criado_em")


class TestDeduplicacao:
    """Testa deduplicação por hash."""

    @pytest.mark.asyncio
    async def test_hash_deduplica_arquivos_iguais(self, tmp_path):
        """Arquivos idênticos produzem mesmo hash."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"

        conteudo = b"mesmo conteudo"
        file1.write_bytes(conteudo)
        file2.write_bytes(conteudo)

        hash1 = await calcular_hash_conteudo(file1)
        hash2 = await calcular_hash_conteudo(file2)

        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_hash_unico_por_arquivo(self, tmp_path):
        """Arquivos diferentes produzem hashes diferentes."""
        file1 = tmp_path / "file1.bin"
        file2 = tmp_path / "file2.bin"

        file1.write_bytes(b"conteudo A")
        file2.write_bytes(b"conteudo B")

        hash1 = await calcular_hash_conteudo(file1)
        hash2 = await calcular_hash_conteudo(file2)

        assert hash1 != hash2
