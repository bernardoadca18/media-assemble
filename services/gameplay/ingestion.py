"""
Fase 9.1 — Pipeline de ingestão de gameplay bruta.

Transforma gravações brutas de sessões de jogo (arquivos longos, sem edição)
em um banco indexado de segmentos curtos aprovados para uso como fundo visual.

Fluxo:
1. Segmentação via ffmpeg (cortes de duração fixa, sem reencode quando possível)
2. Extração de faixa de vídeo apenas (descarta áudio)
3. Filtro de qualidade por movimento (descarta menus, telas paradas, carregamentos)
4. Indexação em banco de dados com metadados
"""
import asyncio
import hashlib
import logging
import math
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from pipeline.config import settings
from db.models import GameplaySegmento

logger = logging.getLogger("services.gameplay.ingestion")


async def segmentar_video(
    video_path: Path,
    duracao_segmento: int,
    output_dir: Path,
) -> list[Path]:
    """
    Segmenta vídeo em partes de duração fixa usando ffmpeg.

    Usa -c copy quando possível (sem reencode), com fallback para reencode
    se o corte exato exigir.

    Args:
        video_path: Caminho do vídeo bruto
        duracao_segmento: Duração de cada segmento em segundos
        output_dir: Diretório para salvar segmentos

    Returns:
        Lista de caminhos dos segmentos criados
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Obter duração total do vídeo
    cmd_duracao = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd_duracao, capture_output=True, text=True, check=True)
        duracao_total = float(result.stdout.strip())
    except Exception as e:
        logger.error("ingestion.erro_duracao", extra={"video": str(video_path), "erro": str(e)})
        return []

    num_segmentos = math.ceil(duracao_total / duracao_segmento)
    segmentos = []

    logger.info(
        "ingestion.segmentando",
        extra={
            "video": str(video_path),
            "duracao_total": duracao_total,
            "num_segmentos": num_segmentos,
        }
    )

    for i in range(num_segmentos):
        start_time = i * duracao_segmento
        output_path = output_dir / f"{video_path.stem}_seg{i:04d}.mp4"

        # Tentar primeiro sem reencode (-c copy)
        cmd_copy = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", str(video_path),
            "-t", str(duracao_segmento),
            "-c", "copy",
            "-an",  # Descarta áudio
            "-avoid_negative_ts", "make_zero",
            str(output_path),
        ]

        try:
            subprocess.run(cmd_copy, capture_output=True, check=True)
            segmentos.append(output_path)
            logger.debug(
                "ingestion.segmento_criado_copy",
                extra={"segmento": str(output_path), "indice": i},
            )
        except subprocess.CalledProcessError:
            # Fallback: reencode necessário
            cmd_encode = [
                "ffmpeg",
                "-y",
                "-ss", str(start_time),
                "-i", str(video_path),
                "-t", str(duracao_segmento),
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "23",
                "-an",  # Descarta áudio
                str(output_path),
            ]

            try:
                subprocess.run(cmd_encode, capture_output=True, check=True)
                segmentos.append(output_path)
                logger.debug(
                    "ingestion.segmento_criado_encode",
                    extra={"segmento": str(output_path), "indice": i},
                )
            except subprocess.CalledProcessError as e:
                logger.error(
                    "ingestion.erro_segmento",
                    extra={"segmento": str(output_path), "indice": i, "erro": str(e)},
                )
                continue

    return segmentos


async def calcular_score_movimento(segmento_path: Path) -> float:
    """
    Calcula score de intensidade de movimento de um segmento.

    Usa filtros do ffmpeg para detectar movimento:
    - mestimate + metadata para calcular vetores de movimento
    - Fallback para signalstats (diferença entre frames)

    Args:
        segmento_path: Caminho do segmento de vídeo

    Returns:
        Score de movimento (0-100, maior = mais movimento)
    """
    # Método 1: Usar mestimate para calcular vetores de movimento
    cmd_motion = [
        "ffmpeg",
        "-i", str(segmento_path),
        "-vf", "mestimate,metadata=print:file=/dev/stdout",
        "-f", "null",
        "-",
    ]

    try:
        result = subprocess.run(cmd_motion, capture_output=True, text=True, timeout=60)

        # Parsear output para extrair valores de movimento
        # Procurar por "mv_name" ou valores de vetores
        lines = result.stderr.split("\n")
        motion_values = []

        for line in lines:
            if "mv" in line.lower() or "motion" in line.lower():
                # Tentar extrair valor numérico
                import re
                numeros = re.findall(r"[\d.]+", line)
                if numeros:
                    try:
                        motion_values.append(float(numeros[0]))
                    except ValueError:
                        continue

        if motion_values:
            # Média dos valores de movimento
            score = sum(motion_values) / len(motion_values)
            # Normalizar para escala 0-100
            return min(100.0, max(0.0, score))

    except subprocess.TimeoutExpired:
        logger.warning("ingestion.timeout_motion", extra={"segmento": str(segmento_path)})
    except Exception as e:
        logger.warning(
            "ingestion.erro_motion_fallback",
            extra={"segmento": str(segmento_path), "erro": str(e)},
        )

    # Fallback: Usar signalstats para detectar diferença entre frames
    cmd_signalstats = [
        "ffmpeg",
        "-i", str(segmento_path),
        "-vf", "signalstats,metadata=print:file=/dev/stdout",
        "-f", "null",
        "-",
    ]

    try:
        result = subprocess.run(cmd_signalstats, capture_output=True, text=True, timeout=60)

        # Extrair valores de diferença (YDIFF, UDIFF, VDIFF)
        import re
        diffs = re.findall(r"(YDIFF|UDIFF|VDIFF):\s*([\d.]+)", result.stderr)

        if diffs:
            diff_values = [float(val) for _, val in diffs]
            # Média das diferenças
            avg_diff = sum(diff_values) / len(diff_values)
            # Normalizar para escala 0-100 (diferença alta = mais movimento)
            score = min(100.0, avg_diff / 10.0)  # Ajuste empírico
            return score

    except Exception as e:
        logger.error(
            "ingestion.erro_signalstats",
            extra={"segmento": str(segmento_path), "erro": str(e)},
        )

    # Se falhar completamente, retorna 0 (sem movimento detectado)
    return 0.0


def classificar_intensidade(score: float) -> str:
    """
    Classifica intensidade de movimento em faixas.

    Args:
        score: Score de movimento (0-100)

    Returns:
        "calmo", "moderado" ou "intenso"
    """
    if score < 15.0:
        return "calmo"
    elif score < 40.0:
        return "moderado"
    else:
        return "intenso"


async def calcular_hash_conteudo(file_path: Path) -> str:
    """
    Calcula hash MD5 do conteúdo do arquivo.

    Args:
        file_path: Caminho do arquivo

    Returns:
        Hash MD5 em hexadecimal
    """
    hash_md5 = hashlib.md5()

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hash_md5.update(chunk)

    return hash_md5.hexdigest()


async def processar_segmento(
    segmento_path: Path,
    jogo_origem: str,
    min_motion_score: float,
) -> Optional[dict]:
    """
    Processa um segmento: calcula movimento, valida qualidade e retorna metadados.

    Args:
        segmento_path: Caminho do segmento
        jogo_origem: Nome do jogo
        min_motion_score: Score mínimo de movimento para aprovar

    Returns:
        Dict com metadados do segmento aprovado, None se reprovado
    """
    # Calcular score de movimento
    score_movimento = await calcular_score_movimento(segmento_path)

    logger.info(
        "ingestion.segmento_analisado",
        extra={
            "segmento": str(segmento_path),
            "score_movimento": score_movimento,
            "minimo": min_motion_score,
        }
    )

    # Verificar se atende ao limiar mínimo
    if score_movimento < min_motion_score:
        logger.info(
            "ingestion.segmento_rejeitado",
            extra={
                "segmento": str(segmento_path),
                "score": score_movimento,
                "motivo": "movimento_insuficiente",
            }
        )
        # Remover segmento rejeitado
        try:
            segmento_path.unlink(missing_ok=True)
        except Exception:
            pass
        return None

    # Obter duração real do segmento
    cmd_duracao = [
        "ffprobe",
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(segmento_path),
    ]

    try:
        result = subprocess.run(cmd_duracao, capture_output=True, text=True, check=True)
        duracao = float(result.stdout.strip())
    except Exception:
        duracao = settings.gameplay_segment_duration_sec

    # Calcular hash para dedup
    hash_conteudo = await calcular_hash_conteudo(segmento_path)

    # Classificar intensidade
    faixa_intensidade = classificar_intensidade(score_movimento)

    return {
        "caminho_arquivo": str(segmento_path),
        "jogo_origem": jogo_origem,
        "duracao_segundos": duracao,
        "score_movimento": score_movimento,
        "faixa_intensidade": faixa_intensidade,
        "hash_conteudo": hash_conteudo,
    }


async def ingerir_arquivo_gameplay(
    arquivo_path: Path,
    jogo: str,
    output_dir: Optional[Path] = None,
    duracao_segmento: Optional[int] = None,
    min_motion_score: Optional[float] = None,
) -> list[str]:
    """
    Processa um arquivo de gameplay bruto completo.

    Fluxo:
    1. Segmenta vídeo em partes de duração fixa
    2. Analisa movimento de cada segmento
    3. Descarta segmentos estáticos (menus, carregamentos)
    4. Persiste segmentos aprovados no banco

    Args:
        arquivo_path: Caminho do arquivo bruto
        jogo: Nome do jogo
        output_dir: Diretório para segmentos (default: settings.gameplay_processed_dir)
        duracao_segmento: Duração em segundos (default: settings)
        min_motion_score: Score mínimo (default: settings)

    Returns:
        Lista de IDs dos segmentos aprovados
    """
    if not arquivo_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {arquivo_path}")

    output_dir = output_dir or Path(settings.gameplay_processed_dir)
    duracao_segmento = duracao_segmento or settings.gameplay_segment_duration_sec
    min_motion_score = min_motion_score or settings.gameplay_min_motion_score

    logger.info(
        "ingestion.iniciando",
        extra={
            "arquivo": str(arquivo_path),
            "jogo": jogo,
            "duracao_segmento": duracao_segmento,
        }
    )

    # Criar diretório temporário para segmentos brutos
    temp_dir = output_dir / f".temp_{arquivo_path.stem}"
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        # 1. Segmentar vídeo
        segmentos = await segmentar_video(
            video_path=arquivo_path,
            duracao_segmento=duracao_segmento,
            output_dir=temp_dir,
        )

        if not segmentos:
            logger.warning("ingestion.sem_segmentos", extra={"arquivo": str(arquivo_path)})
            return []

        # 2. Processar cada segmento
        segmentos_aprovados = []

        for segmento_path in segmentos:
            metadados = await processar_segmento(
                segmento_path=segmento_path,
                jogo_origem=jogo,
                min_motion_score=min_motion_score,
            )

            if metadados:
                # Mover para diretório final
                destino = output_dir / segmento_path.name
                segmento_path.rename(destino)
                metadados["caminho_arquivo"] = str(destino)
                segmentos_aprovados.append(metadados)

        # 3. Persistir no banco
        from db.models import salvar_gameplay_segmentos

        ids = await salvar_gameplay_segmentos(segmentos_aprovados)

        logger.info(
            "ingestion.concluido",
            extra={
                "arquivo": str(arquivo_path),
                "total_segmentos": len(segmentos),
                "aprovados": len(segmentos_aprovados),
            }
        )

        return ids

    finally:
        # Limpar diretório temporário
        try:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass


async def ingerir_diretorio_gameplay(
    diretorio: Path,
    jogo: str,
    output_dir: Optional[Path] = None,
) -> list[str]:
    """
    Processa todos os arquivos de gameplay em um diretório.

    Args:
        diretorio: Diretório com arquivos brutos
        jogo: Nome do jogo
        output_dir: Diretório para segmentos processados

    Returns:
        Lista de IDs de todos os segmentos aprovados
    """
    if not diretorio.exists():
        raise FileNotFoundError(f"Diretório não encontrado: {diretorio}")

    # Extensões de vídeo suportadas
    extensoes = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

    arquivos = [
        f for f in diretorio.iterdir()
        if f.is_file() and f.suffix.lower() in extensoes
    ]

    logger.info(
        "ingestion.diretorio_encontrado",
        extra={"diretorio": str(diretorio), "arquivos": len(arquivos)},
    )

    todos_ids = []

    for arquivo in arquivos:
        try:
            ids = await ingerir_arquivo_gameplay(
                arquivo_path=arquivo,
                jogo=jogo,
                output_dir=output_dir,
            )
            todos_ids.extend(ids)
        except Exception as e:
            logger.error(
                "ingestion.erro_arquivo",
                extra={"arquivo": str(arquivo), "erro": str(e)},
            )
            continue

    return todos_ids
