"""
FASE 3 — Motor de TTS (F5-TTS).

Gera áudio a partir de texto usando F5-TTS zero-shot com voz de referência.
Toda chamada de inferência passa pelo gpu_lock para evitar concorrência de VRAM.
"""
import asyncio
import logging
from pathlib import Path

from pipeline.config import settings
from pipeline.gpu_lock import gpu_task

logger = logging.getLogger("services.audio.tts_engine")

# Instância do modelo carregada lazy (singleton a nível de módulo) — evita
# recarregar os pesos do F5-TTS a cada cena, o que seria lento e
# desnecessário.
_model = None


def _carregar_modelo():
    """
    Carrega o modelo F5-TTS uma única vez (lazy-load, singleton a nível de
    módulo). Usa exclusivamente `f5_tts.api.F5TTS`, que é a interface
    realmente usada por `_sintetizar_sync` — evita manter dois caminhos de
    import divergentes (um deles não utilizado) como havia anteriormente.
    """
    global _model
    if _model is None:
        try:
            from f5_tts.api import F5TTS
        except ImportError as e:
            logger.error("tts_engine.import_falhou", extra={"erro": str(e)})
            raise RuntimeError(
                "F5-TTS não está instalado ou a API mudou de interface "
                "desde a escrita deste wrapper. Instale/verifique conforme "
                "o repositório oficial: https://github.com/SWivid/F5-TTS"
            ) from e

        logger.info("tts_engine.carregando_modelo")
        _model = F5TTS()
        logger.info("tts_engine.modelo_carregado")
    return _model


async def gerar_audio_cena(
    texto: str,
    saida: Path,
    seed: int | None = None,
) -> Path:
    """
    Gera áudio para uma cena usando F5-TTS zero-shot.

    Args:
        texto: Texto da locução a ser sintetizado.
        saida: Caminho do arquivo .wav de saída. Deve ser único por
            tentativa (não reutilizar o mesmo caminho entre retries — ver
            services/audio/pipeline_audio.py) para que o áudio de uma
            tentativa reprovada nunca sobrescreva o de uma tentativa melhor
            já registrada.
        seed: Seed para reprodutibilidade/variação entre tentativas.

    Returns:
        Path do arquivo de áudio gerado (o mesmo `saida` recebido).
    """
    modelo = _carregar_modelo()

    ref_audio_path = Path(settings.f5_tts_ref_audio)
    ref_text = settings.f5_tts_ref_text

    if not ref_audio_path.exists():
        raise FileNotFoundError(
            f"Arquivo de voz de referência não encontrado: {ref_audio_path}"
        )

    saida.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "tts_engine.gerando",
        extra={"texto_len": len(texto), "saida": str(saida), "seed": seed},
    )

    # Inferência protegida pelo lock de GPU — F5-TTS é síncrono, então
    # rodamos em thread separada para não bloquear o event loop enquanto
    # seguramos o lock.
    async with gpu_task(f"tts-{saida.stem}"):
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _sintetizar_sync,
            modelo,
            texto,
            str(ref_audio_path),
            ref_text,
            str(saida),
            seed,
        )

    logger.info("tts_engine.concluido", extra={"saida": str(saida)})
    return saida


def _sintetizar_sync(modelo, texto, ref_audio_path, ref_text, saida_path, seed):
    """
    Síntese síncrona de áudio via F5-TTS.
    Executado em thread separada para não bloquear o event loop.
    """
    try:
        modelo.infer(
            ref_file=ref_audio_path,
            ref_text=ref_text,
            gen_text=texto,
            file_wave=saida_path,
            seed=seed,
        )
    except Exception as e:
        logger.error("tts_engine.sintese_falhou", extra={"erro": str(e)})
        raise