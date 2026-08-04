"""
FASE 3 — Validação de áudio via Faster-Whisper + WER.

Transcreve o áudio gerado e calcula Word Error Rate (WER) para validar
a qualidade da síntese. Usa distância de Levenshtein em nível de palavra.
"""
import asyncio
import logging
import re
from pathlib import Path

from pipeline.config import settings
from pipeline.gpu_lock import gpu_task
from pipeline.schemas import Palavra

logger = logging.getLogger("services.audio.validator")

# Modelo Whisper carregado lazy (singleton a nível de módulo)
_whisper_model = None


def _carregar_whisper():
    """
    Carrega o modelo Faster-Whisper uma única vez (lazy-load).
    """
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel

            logger.info(
                "validator.carregando_whisper",
                extra={
                    "model": settings.whisper_model_size,
                    "device": settings.whisper_device,
                    "compute_type": settings.whisper_compute_type,
                }
            )

            _whisper_model = WhisperModel(
                settings.whisper_model_size,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )

            logger.info("validator.whisper_carregado")
        except ImportError as e:
            logger.error("validator.import_falhou", extra={"erro": str(e)})
            raise RuntimeError(
                "Faster-Whisper não está instalado. Execute: pip install faster-whisper"
            ) from e
    return _whisper_model


def _normalizar_texto(texto: str) -> str:
    """
    Normaliza texto para comparação de WER.
    - Converte para minúsculas
    - Remove pontuação
    - Normaliza espaços
    """
    # Remove pontuação (mantém apenas letras, números e espaços)
    texto = re.sub(r'[^\w\s]', '', texto.lower())
    # Normaliza espaços múltiplos
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


def _calcular_wer(referencia: str, hipotese: str) -> float:
    """
    Calcula Word Error Rate usando distância de Levenshtein em nível de palavra.

    WER = (substituições + inserções + deleções) / total_de_palavras_referência

    Args:
        referencia: Texto esperado (ground truth).
        hipotese: Texto transcrito (hipótese).

    Returns:
        WER como float entre 0.0 e 1.0.
    """
    ref_words = _normalizar_texto(referencia).split()
    hyp_words = _normalizar_texto(hipotese).split()

    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0

    # Matriz de distância de Levenshtein
    m, n = len(ref_words), len(hyp_words)
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # Inicialização
    for i in range(m + 1):
        dp[i][0] = i  # deleções
    for j in range(n + 1):
        dp[0][j] = j  # inserções

    # Preenchimento
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_words[i - 1] == hyp_words[j - 1]:
                dp[i][j] = dp[i - 1][j - 1]  # match
            else:
                dp[i][j] = 1 + min(
                    dp[i - 1][j],     # deleção
                    dp[i][j - 1],     # inserção
                    dp[i - 1][j - 1]  # substituição
                )

    distancia = dp[m][n]
    wer = distancia / m

    return wer


async def validar_audio(
    caminho_audio: Path,
    texto_esperado: str,
    limite_wer: float | None = None
) -> tuple[float, list[Palavra]]:
    """
    Valida áudio transcrevendo com Faster-Whisper e calculando WER.

    Args:
        caminho_audio: Caminho do arquivo de áudio (.wav).
        texto_esperado: Texto que deveria estar no áudio.
        limite_wer: Limite de WER para aprovação. Usa settings.wer_limite_aprovacao se None.

    Returns:
        Tupla (wer, palavras_transcritas) onde:
        - wer: Word Error Rate calculado
        - palavras_transcritas: Lista de Palavra com timestamps

    Raises:
        FileNotFoundError: Se o arquivo de áudio não existir.
    """
    if not caminho_audio.exists():
        raise FileNotFoundError(f"Arquivo de áudio não encontrado: {caminho_audio}")

    if limite_wer is None:
        limite_wer = settings.wer_limite_aprovacao

    model = _carregar_whisper()

    logger.info(
        "validator.transcrevendo",
        extra={"audio": str(caminho_audio), "limite_wer": limite_wer}
    )

    # Transcrição protegida pelo lock de GPU
    async with gpu_task(f"whisper-{caminho_audio.stem}"):
        loop = asyncio.get_event_loop()
        segments, info = await loop.run_in_executor(
            None,
            _transcrever_sync,
            model,
            str(caminho_audio),
        )

    # Extrai palavras com timestamps
    palavras = []
    texto_transcrito = []

    for segment in segments:
        texto_transcrito.append(segment.text)
        if segment.words:
            for word in segment.words:
                palavras.append(Palavra(
                    text=word.word.strip(),
                    start=word.start,
                    end=word.end,
                ))

    texto_transcrito_completo = " ".join(texto_transcrito)
    wer = _calcular_wer(texto_esperado, texto_transcrito_completo)

    logger.info(
        "validator.validado",
        extra={
            "wer": wer,
            "limite": limite_wer,
            "aprovado": wer <= limite_wer,
            "duracao_audio": info.duration,
        }
    )

    return wer, palavras


def _transcrever_sync(model, caminho_audio: str):
    """
    Transcrição síncrona via Faster-Whisper.
    Executado em thread separada para não bloquear o event loop.
    """
    segments, info = model.transcribe(
        caminho_audio,
        word_timestamps=True,
        language="pt",
    )
    # Converte generators para listas (necessário fora do contexto do model)
    return list(segments), info
