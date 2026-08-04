"""
FASE 3 — Pipeline de áudio completo.

Orquestra a geração de áudio (TTS), validação (Whisper + WER) e concatenação
para todas as cenas de um roteiro.
"""
import logging
import random
import tempfile
from pathlib import Path

from pipeline.config import settings
from pipeline.schemas import Cena, Roteiro
from services.audio.mixer import concatenar_audios
from services.audio.tts_engine import gerar_audio_cena
from services.audio.validator import validar_audio

logger = logging.getLogger("services.audio.pipeline_audio")


def _limpar_tentativas_descartadas(tentativas_paths: list[Path], manter: Path) -> None:
    """
    Remove os arquivos de tentativas de TTS que não foram escolhidas, para
    não acumular lixo em disco a cada cena processada. `missing_ok=True`
    também cobre o caso de testes com TTS mockado, onde os arquivos nunca
    chegam a ser criados de fato.
    """
    for path in tentativas_paths:
        if path != manter:
            path.unlink(missing_ok=True)


async def gerar_e_validar_cena(
    cena: Cena,
    dir_temp: Path,
    max_tentativas: int | None = None,
) -> tuple[Path, float, list]:
    """
    Gera e valida áudio para uma única cena com retry por seed.

    Cada tentativa é escrita em um arquivo PRÓPRIO (`cena_XXX_tentativa_N.wav`)
    — nunca no mesmo caminho entre tentativas. Isso é intencional: se todas
    as tentativas escrevessem no mesmo arquivo, uma tentativa pior gerada
    por último sobrescreveria no disco uma tentativa melhor já registrada
    em memória, e `cena.audio_path`/`cena.wer_final` ficariam
    inconsistentes com o áudio realmente salvo.

    Tenta gerar e validar até `max_tentativas` vezes. Se esgotar as
    tentativas sem aprovar, aceita a melhor tentativa observada (menor WER)
    e marca `revisao_manual_necessaria = True`.

    Args:
        cena: Cena com texto_locucao preenchido.
        dir_temp: Diretório temporário para os áudios.
        max_tentativas: Máximo de tentativas. Usa settings.max_tentativas_tts se None.

    Returns:
        Tupla (caminho_audio, wer, palavras_transcritas) referente à
        tentativa escolhida (aprovada, ou a melhor entre as reprovadas).

    Side effects:
        - Preenche cena.audio_path, cena.palavras_transcritas, cena.wer_final
        - Define cena.revisao_manual_necessaria = True se esgotar tentativas
        - Remove do disco os arquivos das tentativas não escolhidas
    """
    if max_tentativas is None:
        max_tentativas = settings.max_tentativas_tts

    melhor_wer = float("inf")
    melhor_palavras: list = []
    melhor_audio_path: Path | None = None
    tentativas_paths: list[Path] = []

    for tentativa in range(1, max_tentativas + 1):
        # Seed diferente a cada tentativa para variação na síntese
        seed = random.randint(1, 100000) if tentativa > 1 else None
        caminho_tentativa = dir_temp / f"cena_{cena.cena_id:03d}_tentativa_{tentativa}.wav"
        tentativas_paths.append(caminho_tentativa)

        try:
            await gerar_audio_cena(
                texto=cena.texto_locucao,
                saida=caminho_tentativa,
                seed=seed,
            )

            wer, palavras = await validar_audio(
                caminho_audio=caminho_tentativa,
                texto_esperado=cena.texto_locucao,
            )

            if wer < melhor_wer:
                melhor_wer = wer
                melhor_palavras = palavras
                melhor_audio_path = caminho_tentativa

            if wer <= settings.wer_limite_aprovacao:
                logger.info(
                    "pipeline_audio.cena_aprovada",
                    extra={"cena_id": cena.cena_id, "tentativa": tentativa, "wer": wer},
                )
                cena.audio_path = str(caminho_tentativa)
                cena.palavras_transcritas = palavras
                cena.wer_final = wer
                cena.revisao_manual_necessaria = False
                _limpar_tentativas_descartadas(tentativas_paths, manter=caminho_tentativa)
                return caminho_tentativa, wer, palavras

            logger.warning(
                "pipeline_audio.wer_alto",
                extra={
                    "cena_id": cena.cena_id,
                    "tentativa": tentativa,
                    "wer": wer,
                    "limite": settings.wer_limite_aprovacao,
                },
            )

        except Exception as e:
            logger.error(
                "pipeline_audio.tentativa_falhou",
                extra={"cena_id": cena.cena_id, "tentativa": tentativa, "erro": str(e)},
            )
            continue

    # Esgotou tentativas - aceita a melhor observada
    if melhor_audio_path is not None:
        logger.warning(
            "pipeline_audio.tentativas_esgotadas",
            extra={"cena_id": cena.cena_id, "melhor_wer": melhor_wer, "revisao_manual": True},
        )
        cena.audio_path = str(melhor_audio_path)
        cena.palavras_transcritas = melhor_palavras
        cena.wer_final = melhor_wer
        cena.revisao_manual_necessaria = True
        _limpar_tentativas_descartadas(tentativas_paths, manter=melhor_audio_path)
        return melhor_audio_path, melhor_wer, melhor_palavras

    # Não conseguiu gerar nenhum áudio (todas as tentativas lançaram exceção)
    raise RuntimeError(f"Não foi possível gerar áudio para cena {cena.cena_id}")


async def gerar_audio_do_roteiro(
    roteiro: Roteiro,
    dir_temp: Path | None = None,
) -> Roteiro:
    """
    Gera todo o áudio para um roteiro completo.

    Para cada cena:
    1. Gera áudio via F5-TTS
    2. Valida via Faster-Whisper + WER
    3. Retry com seeds diferentes se WER alto

    Depois concatena todos os áudios em um áudio master.

    Args:
        roteiro: Roteiro com cenas preenchidas.
        dir_temp: Diretório temporário. Cria temp dir se None.

    Returns:
        Roteiro com audio_path e palavras_transcritas preenchidos em cada cena,
        e metadata.audio_final_path + metadata.palavras_transcritas atualizados.
    """
    if dir_temp is None:
        dir_temp = Path(tempfile.mkdtemp(prefix="audio_pipeline_"))

    dir_temp = Path(dir_temp)
    dir_temp.mkdir(parents=True, exist_ok=True)

    logger.info(
        "pipeline_audio.iniciando",
        extra={
            "video_id": roteiro.metadata.video_id,
            "total_cenas": len(roteiro.cenas),
            "dir_temp": str(dir_temp),
        },
    )

    for i, cena in enumerate(roteiro.cenas):
        logger.info(
            "pipeline_audio.processando_cena",
            extra={
                "video_id": roteiro.metadata.video_id,
                "cena_id": cena.cena_id,
                "ordem": i + 1,
                "total": len(roteiro.cenas),
            },
        )
        await gerar_e_validar_cena(cena, dir_temp)

    audio_master, palavras_absolutas = await concatenar_audios(
        cenas=roteiro.cenas,
        dir_temp=dir_temp,
    )

    roteiro.metadata.audio_final_path = audio_master
    roteiro.metadata.palavras_transcritas = palavras_absolutas

    wers = [c.wer_final for c in roteiro.cenas if c.wer_final is not None]
    wer_medio = sum(wers) / len(wers) if wers else 0.0
    cenas_revisao = sum(1 for c in roteiro.cenas if c.revisao_manual_necessaria)

    logger.info(
        "pipeline_audio.concluido",
        extra={
            "video_id": roteiro.metadata.video_id,
            "audio_master": audio_master,
            "wer_medio": wer_medio,
            "cenas_revisao": cenas_revisao,
            "total_palavras": len(palavras_absolutas),
        },
    )

    return roteiro