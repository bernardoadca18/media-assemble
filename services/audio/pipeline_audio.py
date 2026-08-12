"""
FASE 3 Pipeline de áudio completo (REFATORADO).

Orquestra geração de áudio (Kokoro+Seed-VC), validação (Whisper + WER) e concatenação
para todas as cenas de um roteiro.
"""
import gc
import logging
import shutil
import tempfile
from pathlib import Path

from pipeline.config import settings
from pipeline.schemas import Cena, Roteiro, Palavra
from pipeline.gpu_lock import gpu_task
from services.audio.mixer import concatenar_audios
from services.audio.validator import validar_audio, liberar_modelo_whisper
from services.audio.timbre_variation import aplicar_variacao_timbre, obter_perfil_voz_canal
from services.audio.glossario_fonetico import aplicar_glossario
from services.audio.voice_pipeline_client import get_voice_pipeline_client

logger = logging.getLogger("services.audio.pipeline_audio")


async def _gerar_e_validar_cena(
    cena: Cena,
    dir_temp: Path,
    run_name: str | None = None,
    max_tentativas: int | None = None,
    canal_id: str | None = None,
    config_nicho: "ConfigNicho | None" = None,
) -> tuple[Path, float, list[Palavra]]:
    """
    Gera e valida áudio para uma cena usando Kokoro+Seed-VC.

    Args:
        cena: Cena com texto_locucao
        dir_temp: Diretório temporário
        run_name: Perfil de voz treinado
        max_tentativas: Máximo de tentativas (default: settings.max_tentativas_tts)
        canal_id: ID do canal (para variação de timbre opcional)
        config_nicho: Configuração do nicho (para overrides de voz)

    Returns:
        Tupla (caminho_audio, wer, palavras_transcritas)

    Side effects:
        - Preenche cena.audio_path, cena.palavras_transcritas, cena.wer_final
        - Preenche cena.run_name_usado, cena.tempo_sintese_segundos
        - Define cena.revisao_manual_necessaria = True se esgotar tentativas
        - Remove do disco os arquivos das tentativas não escolhidas
    """
    if max_tentativas is None:
        max_tentativas = settings.max_tentativas_tts

    # Determina run_name (perfil de voz) a usar
    if run_name is None:
        run_name = config_nicho.voz_run_name if config_nicho else settings.voice_pipeline_run_name_default

    # Aplica glossário fonético ao texto ANTES de enviar ao Kokoro
    # (mantém texto original em cena.texto_locucao para legendas e validação)
    texto_para_kokoro = aplicar_glossario(cena.texto_locucao)

    client = get_voice_pipeline_client()

    melhor_wer = float("inf")
    melhor_palavras: list[Palavra] = []
    melhor_audio_path: Path | None = None
    melhor_tempo_sintese: float | None = None

    tentativas_paths: list[Path] = []

    for tentativa in range(1, max_tentativas + 1):
        caminho_tentativa = dir_temp / f"cena_{cena.cena_id:03d}_tentativa_{tentativa}.wav"
        tentativas_paths.append(caminho_tentativa)

        try:
            logger.info(
                "pipeline_audio.gerando_cena",
                extra={
                    "cena_id": cena.cena_id,
                    "tentativa": tentativa,
                    "max_tentativas": max_tentativas,
                    "run_name": run_name,
                }
            )

            # Gera áudio via API Kokoro+Seed-VC
            audio_path, tempo_sintese = await client.narrar(
                texto=texto_para_kokoro,
                run_name=run_name,
                output_path=caminho_tentativa,
            )

            # Fase 9.3 — Aplicar variação de timbre OPCIONAL (pós-processamento)
            audio_para_validar = audio_path
            if canal_id:
                pitch_shift, velocidade = obter_perfil_voz_canal(canal_id, config_nicho)
                if abs(pitch_shift) > 0.01 or abs(velocidade - 1.0) > 0.01:
                    audio_para_validar = await aplicar_variacao_timbre(
                        audio_path=audio_path,
                        canal_id=canal_id,
                        pitch_shift=pitch_shift,
                        velocidade=velocidade,
                        saida=dir_temp / f"cena_{cena.cena_id:03d}_timbre_var_{tentativa}.wav",
                    )

            # Validação via Whisper + WER (mantido do sistema original)
            wer, palavras = await validar_audio(
                caminho_audio=audio_para_validar,
                texto_esperado=cena.texto_locucao,  # Texto ORIGINAL (sem glossário)
            )

            logger.info(
                "pipeline_audio.validado",
                extra={
                    "cena_id": cena.cena_id,
                    "tentativa": tentativa,
                    "wer": wer,
                    "limite": settings.wer_limite_aprovacao,
                }
            )

            # Atualiza melhor tentativa
            if wer < melhor_wer:
                melhor_wer = wer
                melhor_palavras = palavras
                melhor_audio_path = audio_para_validar
                melhor_tempo_sintese = tempo_sintese

            # Se passou no WER, usa este áudio
            if wer <= settings.wer_limite_aprovacao:
                logger.info(
                    "pipeline_audio.cena_aprovada",
                    extra={
                        "cena_id": cena.cena_id,
                        "tentativa": tentativa,
                        "wer": wer,
                    }
                )
                break

        except Exception as e:
            logger.error(
                "pipeline_audio.erro_tentativa",
                extra={
                    "cena_id": cena.cena_id,
                    "tentativa": tentativa,
                    "erro": str(e),
                },
                exc_info=True,
            )
            continue

    # Verifica se conseguiu gerar pelo menos um áudio
    if melhor_audio_path is not None:
        cena.audio_path = str(melhor_audio_path)
        cena.palavras_transcritas = melhor_palavras
        cena.wer_final = melhor_wer
        cena.run_name_usado = run_name
        cena.tempo_sintese_segundos = melhor_tempo_sintese

        if melhor_wer > settings.wer_limite_aprovacao:
            cena.revisao_manual_necessaria = True

        _limpar_tentativas_descartadas(tentativas_paths, manter=melhor_audio_path)
        return melhor_audio_path, melhor_wer, melhor_palavras

    # Não conseguiu gerar nenhum áudio
    raise RuntimeError(f"Não foi possível gerar áudio para cena {cena.cena_id}")


def _limpar_tentativas_descartadas(tentativas_paths: list[Path], manter: Path) -> None:
    """
    Remove arquivos de tentativas TTS que não foram escolhidas,
    para não acumular lixo em disco a cada cena processada.
    """
    for path in tentativas_paths:
        if path != manter:
            path.unlink(missing_ok=True)


async def gerar_audio_do_roteiro(
    roteiro: Roteiro,
    dir_temp: Path | None = None,
) -> Roteiro:
    """
    Gera todo o áudio para um roteiro completo.

    Para cada cena:
    1. Gera áudio via Kokoro+Seed-VC (API externa)
    2. Aplica glossário fonético automaticamente
    3. Valida via Faster-Whisper + WER
    4. Retry com novo texto se WER alto
    5. Aplica variação de timbre opcional (pós-processamento)

    Depois concatena todos os áudios em um áudio master.

    Args:
        roteiro: Roteiro com cenas preenchidas.
        dir_temp: Diretório temporário. Cria temp dir se None.

    Returns:
        Roteiro com audio_path e palavras_transcritas preenchidos em cada cena,
        metadata.audio_final_path e metadata.palavras_transcritas atualizados.
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
        }
    )

    # Obtém config do nicho se disponível
    from pipeline.nichos import obter_config_nicho
    config_nicho = None
    try:
        config_nicho = obter_config_nicho(roteiro.metadata.nicho)
    except Exception:
        logger.warning("pipeline_audio.config_nicho_nao_encontrado")

    # Determina run_name para este roteiro
    run_name = config_nicho.voz_run_name if config_nicho else settings.voice_pipeline_run_name_default

    # Processa cada cena sequencialmente
    total_tempo_sintese = 0.0
    for i, cena in enumerate(roteiro.cenas, 1):
        logger.info(
            "pipeline_audio.processando_cena",
            extra={
                "video_id": roteiro.metadata.video_id,
                "cena_id": cena.cena_id,
                "progresso": f"{i}/{len(roteiro.cenas)}",
            }
        )

        try:
            audio_path, wer, palavras = await _gerar_e_validar_cena(
                cena=cena,
                dir_temp=dir_temp,
                run_name=run_name,
                canal_id=roteiro.metadata.canal_id if hasattr(roteiro.metadata, 'canal_id') else None,
                config_nicho=config_nicho,
            )

            if cena.tempo_sintese_segundos:
                total_tempo_sintese += cena.tempo_sintese_segundos

        except Exception as e:
            logger.error(
                "pipeline_audio.falha_cena",
                extra={
                    "video_id": roteiro.metadata.video_id,
                    "cena_id": cena.cena_id,
                    "erro": str(e),
                },
                exc_info=True,
            )
            raise

    # Concatena todos os áudios em um áudio master
    audio_master_path, palavras_absolutas = await concatenar_audios(
        cenas=roteiro.cenas,
        dir_temp=dir_temp,
    )

    # Atualiza metadata do roteiro
    roteiro.metadata.audio_final_path = audio_master_path
    roteiro.metadata.palavras_transcritas = palavras_absolutas

    logger.info(
        "pipeline_audio.audio_master_criado",
        extra={
            "video_id": roteiro.metadata.video_id,
            "audio_master_path": audio_master_path,
            "total_palavras": len(palavras_absolutas),
            "tempo_total_sintese": total_tempo_sintese,
        }
    )

    # Copia áudio master para remotion/public (Fase 5)
    remotion_public_dir = Path("remotion/public")
    remotion_public_dir.mkdir(parents=True, exist_ok=True)
    audio_public_path = remotion_public_dir / f"audio_{roteiro.metadata.video_id}.wav"
    shutil.copy2(audio_master_path, audio_public_path)

    # Atualiza o path no roteiro para o caminho relativo em public/
    roteiro.metadata.audio_final_path = f"audio_{roteiro.metadata.video_id}.wav"

    logger.info(
        "pipeline_audio.audio_copiado_para_public",
        extra={
            "original": str(audio_master_path),
            "public": str(audio_public_path),
        }
    )

    # LIBERAÇÃO DE MEMÓRIA - Fase 3 completa
    # Libera modelo Whisper da memória GPU/RAM
    logger.info("pipeline_audio.liberando_modelos")
    liberar_modelo_whisper()

    # Limpa diretório temporário se foi criado por esta função
    if dir_temp and dir_temp.exists():
        try:
            shutil.rmtree(dir_temp)
            logger.info("pipeline_audio.temp_limpado", extra={"dir_temp": str(dir_temp)})
        except Exception as e:
            logger.warning("pipeline_audio.erro_limpar_temp", extra={"erro": str(e)})

    # Força garbage collection
    gc.collect()

    return roteiro
