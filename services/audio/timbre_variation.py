"""
Fase 9.3 — Variação de timbre por canal.

Aplica pitch shift e ajuste de velocidade ao áudio gerado pelo F5-TTS
para criar variações de voz determinísticas por canal, permitindo usar
uma única referência de voz para múltiplos canais com timbres distintos.
"""
import hashlib
import logging
import subprocess
import tempfile
from pathlib import Path

from pipeline.config import settings

logger = logging.getLogger("services.audio.timbre_variation")


def calcular_variacao_canal(canal_id: str) -> tuple[float, float]:
    """
    Calcula valores determinísticos de pitch shift e velocidade para um canal.

    Usa hash do canal_id mapeado para as faixas configuradas, garantindo que
    o mesmo canal sempre receba os mesmos valores de variação.

    Args:
        canal_id: ID único do canal

    Returns:
        Tupla (pitch_shift_semitons, velocidade_fala) com valores dentro
        das faixas configuradas em settings.
    """
    # Hash determinístico do canal_id
    hash_bytes = hashlib.sha256(canal_id.encode()).digest()

    # Usa os primeiros 4 bytes para pitch shift (0-255 mapeado para faixa)
    pitch_normalized = hash_bytes[0] / 255.0
    pitch_shift = settings.timbre_pitch_shift_min + pitch_normalized * (
        settings.timbre_pitch_shift_max - settings.timbre_pitch_shift_min
    )

    # Usa os bytes 4-7 para velocidade (0-255 mapeado para faixa)
    speed_normalized = hash_bytes[4] / 255.0
    velocidade = settings.timbre_velocidade_min + speed_normalized * (
        settings.timbre_velocidade_max - settings.timbre_velocidade_min
    )

    logger.debug(
        "timbre_variation.variacao_calculada",
        extra={
            "canal_id": canal_id,
            "pitch_shift": pitch_shift,
            "velocidade": velocidade,
        },
    )

    return pitch_shift, velocidade


async def aplicar_variacao_timbre(
    audio_path: Path,
    canal_id: str,
    pitch_shift: float | None = None,
    velocidade: float | None = None,
    output_path: Path | None = None,
) -> Path:
    """
    Aplica variação de timbre a um arquivo de áudio.

    Se pitch_shift ou velocidade não forem fornecidos, calcula valores
    determinísticos a partir do canal_id.

    Args:
        audio_path: Caminho do arquivo de áudio original
        canal_id: ID do canal para variação determinística
        pitch_shift: Shift em semitons (-2.0 a +2.0), None = determinístico
        velocidade: Velocidade de fala (0.95 a 1.05), None = determinístico
        output_path: Caminho de saída, None = arquivo temporário

    Returns:
        Path do arquivo de áudio com variação aplicada

    Raises:
        RuntimeError: Se ffmpeg falhar na aplicação do filtro
    """
    # Calcular valores se não fornecidos
    if pitch_shift is None or velocidade is None:
        pitch_auto, vel_auto = calcular_variacao_canal(canal_id)
        pitch_shift = pitch_shift if pitch_shift is not None else pitch_auto
        velocidade = velocidade if velocidade is not None else vel_auto

    # Se não há variação significativa, retornar original
    if abs(pitch_shift) < 0.01 and abs(velocidade - 1.0) < 0.01:
        logger.debug(
            "timbre_variation.sem_variacao",
            extra={"audio_path": str(audio_path)},
        )
        return audio_path

    # Definir caminho de saída
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".wav", prefix="timbre_var_"))
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "timbre_variation.aplicando",
        extra={
            "audio_path": str(audio_path),
            "pitch_shift": pitch_shift,
            "velocidade": velocidade,
            "output_path": str(output_path),
        },
    )

    # Construir filtro ffmpeg
    # rubberband é mais estável para pitch shift com qualidade
    # atempo para ajuste de velocidade
    # Ordem: primeiro pitch shift, depois velocidade

    filters = []

    # Pitch shift via asetrate (mais simples que rubberband)
    # asetrate multiplica a taxa de amostragem, alterando pitch
    # Fator: 2^(semitons/12)
    if abs(pitch_shift) >= 0.01:
        pitch_factor = 2 ** (pitch_shift / 12.0)
        filters.append(f"asetrate=44100*{pitch_factor:.6f},aresample=44100")

    # Velocidade via atempo
    # atempo aceita valores de 0.5 a 2.0
    if abs(velocidade - 1.0) >= 0.01:
        # Se velocidade estiver fora da faixa do atempo, encadear múltiplos
        if velocidade < 0.5 or velocidade > 2.0:
            # Velocidade dentro da faixa configurada (0.95-1.05), não deve acontecer
            logger.warning(
                "timbre_variation.velocidade_fora_faixa",
                extra={"velocidade": velocidade},
            )
        filters.append(f"atempo={velocidade:.4f}")

    if not filters:
        return audio_path

    filter_str = ",".join(filters)

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(audio_path),
        "-filter:a", filter_str,
        "-c:a", "pcm_s16le",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )

        logger.info(
            "timbre_variation.aplicado",
            extra={"output_path": str(output_path)},
        )

        return output_path

    except subprocess.CalledProcessError as e:
        logger.error(
            "timbre_variation.erro_ffmpeg",
            extra={"stderr": e.stderr, "stdout": e.stdout},
        )
        raise RuntimeError(f"Falha ao aplicar variação de timbre: {e.stderr}")


def obter_perfil_voz_canal(
    canal_id: str,
    config_nicho: "ConfigNicho | None" = None,
) -> tuple[float, float]:
    """
    Obtém perfil de voz para um canal, usando config do nicho ou valores determinísticos.

    Args:
        canal_id: ID do canal
        config_nicho: Configuração do nicho com overrides manuais

    Returns:
        Tupla (pitch_shift_semitons, velocidade_fala)
    """
    # Calcular valores determinísticos como base
    pitch_default, vel_default = calcular_variacao_canal(canal_id)

    # Se há overrides no nicho, usá-los; caso contrário, usar determinísticos
    pitch = pitch_default
    velocidade = vel_default

    if config_nicho is not None:
        if config_nicho.pitch_shift_semitons is not None:
            pitch = config_nicho.pitch_shift_semitons
            logger.debug(
                "timbre_variation.pitch_override",
                extra={
                    "canal_id": canal_id,
                    "pitch": pitch,
                },
            )
        if config_nicho.velocidade_fala is not None:
            velocidade = config_nicho.velocidade_fala
            logger.debug(
                "timbre_variation.velocidade_override",
                extra={
                    "canal_id": canal_id,
                    "velocidade": velocidade,
                },
            )

    return pitch, velocidade
