"""
FASE 3 — Concatenação/mixagem de áudio via FFmpeg.

Concatena os áudios individuais de cada cena em um áudio master final.
Ajusta timestamps das palavras transcritas para serem absolutos em relação
ao áudio master (essencial para legendas na Fase 5).
"""
import asyncio
import logging
import tempfile
from pathlib import Path

from pipeline.schemas import Cena, Palavra

logger = logging.getLogger("services.audio.mixer")


async def concatenar_audios(cenas: list[Cena], dir_temp: Path) -> tuple[str, list[Palavra]]:
    """
    Concatena áudios das cenas em um áudio master via FFmpeg concat demuxer.

    Args:
        cenas: Lista de cenas com audio_path preenchido.
        dir_temp: Diretório temporário para o arquivo de lista e saída.

    Returns:
        Tupla (caminho_audio_master, palavras_com_timestamps_absolutos) onde:
        - caminho_audio_master: Caminho do arquivo .wav final concatenado
        - palavras_com_timestamps_absolutos: Todas as palavras das cenas com
          timestamps ajustados para o tempo absoluto do áudio master

    Raises:
        ValueError: Se alguma cena não tiver audio_path.
        RuntimeError: Se o FFmpeg falhar.
    """
    # Valida que todas as cenas têm áudio
    for i, cena in enumerate(cenas):
        if not cena.audio_path:
            raise ValueError(f"Cena {cena.cena_id} (índice {i}) não tem audio_path")
        if not Path(cena.audio_path).exists():
            raise FileNotFoundError(f"Áudio da cena {cena.cena_id} não encontrado: {cena.audio_path}")

    # Cria arquivo de lista para o concat demuxer do FFmpeg
    dir_temp.mkdir(parents=True, exist_ok=True)
    lista_file = dir_temp / "concat_list.txt"
    audio_master_path = dir_temp / "audio_master.wav"

    with open(lista_file, "w") as f:
        for cena in cenas:
            # Caminho absoluto para evitar problemas
            audio_absoluto = Path(cena.audio_path).resolve()
            f.write(f"file '{audio_absoluto}'\n")

    logger.info(
        "mixer.concatenando",
        extra={
            "total_cenas": len(cenas),
            "lista_file": str(lista_file),
            "saida": str(audio_master_path),
        }
    )

    # Executa FFmpeg
    cmd = [
        "ffmpeg",
        "-y",  # Sobrescreve se existir
        "-f", "concat",
        "-safe", "0",
        "-i", str(lista_file),
        "-c", "copy",  # Sem re-encode (rápido e sem perda)
        str(audio_master_path),
    ]

    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        _executar_ffmpeg,
        cmd,
    )

    if result["returncode"] != 0:
        logger.error("mixer.ffmpeg_falhou", extra={"stderr": result["stderr"]})
        raise RuntimeError(f"FFmpeg falhou: {result['stderr']}")

    # Calcula timestamps absolutos
    palavras_absolutas = _ajustar_timestamps_absolutos(cenas)

    logger.info(
        "mixer.concluido",
        extra={
            "audio_master": str(audio_master_path),
            "total_palavras": len(palavras_absolutas),
        }
    )

    return str(audio_master_path), palavras_absolutas


def _executar_ffmpeg(cmd: list[str]) -> dict:
    """
    Executa comando FFmpeg de forma síncrona.
    """
    import subprocess

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    return {
        "returncode": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _obter_duracao_audio(caminho: str | None) -> float | None:
    """
    Retorna a duração real (em segundos) do arquivo de áudio, ou None se
    não for possível determinar (arquivo inexistente, formato não
    suportado, etc. — cenário comum em testes com TTS mockado).
    """
    if not caminho:
        return None
    try:
        import librosa

        return float(librosa.get_duration(path=caminho))
    except Exception as e:
        logger.debug("mixer.duracao_indisponivel", extra={"caminho": caminho, "erro": str(e)})
        return None


def _ajustar_timestamps_absolutos(cenas: list[Cena]) -> list[Palavra]:
    """
    Ajusta timestamps das palavras para serem absolutos em relação ao áudio master.

    Cada cena tem seus próprios timestamps relativos (0 = início daquele áudio).
    Precisamos somar a duração de todas as cenas anteriores para obter o tempo
    absoluto no áudio master.

    A duração usada para o offset é, em ordem de preferência:
    1. A duração REAL do arquivo de áudio da cena (via `librosa` — é o que
       o FFmpeg de fato usa ao concatenar, então é a fonte mais confiável;
       o fim da última palavra transcrita pelo Whisper costuma ficar um
       pouco antes do fim real do clipe, e esse pequeno resíduo se acumula
       cena após cena ao longo do vídeo).
    2. Se o áudio não estiver disponível para leitura (ex: testes com TTS
       mockado), cai para o fim da última palavra transcrita.
    3. Na ausência de ambos, usa a duração estimada declarada no roteiro.

    Args:
        cenas: Lista de cenas com palavras_transcritas preenchidas.

    Returns:
        Lista de todas as palavras com timestamps absolutos.
    """
    palavras_absolutas = []
    offset_atual = 0.0  # Offset acumulado em segundos

    for cena in cenas:
        if cena.palavras_transcritas:
            for palavra in cena.palavras_transcritas:
                palavras_absolutas.append(Palavra(
                    text=palavra.text,
                    start=palavra.start + offset_atual,
                    end=palavra.end + offset_atual,
                ))

        duracao_real = _obter_duracao_audio(cena.audio_path)
        if duracao_real is not None:
            duracao_cena = duracao_real
        elif cena.palavras_transcritas:
            ultima_palavra = max(cena.palavras_transcritas, key=lambda p: p.end)
            duracao_cena = ultima_palavra.end
        else:
            duracao_cena = cena.duracao_estimada_segundos

        offset_atual += duracao_cena

    return palavras_absolutas