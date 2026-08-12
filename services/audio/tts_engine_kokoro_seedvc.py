"""
Implementação concreta de TTSEngine usando Kokoro + Seed-VC.

Esta engine comunica-se com o serviço externo via API HTTP /narrar.
"""
from pathlib import Path

from services.audio.tts_engine_base import TTSEngine, TTSError, SinteseFalhouError
from services.audio.voice_pipeline_client import (
    VoicePipelineClient,
    RunNameInvalido,
    GPUOcupada,
    PipelineInternoFalhou,
    get_voice_pipeline_client,
)
from services.audio.validator import validar_audio
from pipeline.config import settings


class KokoroSeedVCEngine(TTSEngine):
    """
    Engine de TTS usando pipeline Kokoro + Seed-VC.

    Características:
    - Comunicação via API HTTP com serviço externo
    - Suporte a múltiplos perfis de voz (run_name)
    - Validação WER via Faster-Whisper
    - Glossário fonético automático
    """

    def __init__(self, client: VoicePipelineClient | None = None):
        self.client = client or get_voice_pipeline_client()

    async def sintetizar(
        self,
        texto: str,
        output_path: Path,
        run_name: str | None = None,
        **kwargs
    ) -> Path:
        """
        Sintetiza áudio via API Kokoro+Seed-VC.

        Args:
            texto: Texto a ser sintetizado
            output_path: Caminho para salvar o áudio
            run_name: Perfil de voz treinado (default: configuração global)
            **kwargs: Ignorados (compatibilidade com interface)

        Returns:
            Path do arquivo de áudio

        Raises:
            SinteseFalhouError: Se a síntese falhar após retries
        """
        try:
            audio_path, tempo_sintese = await self.client.narrar(
                texto=texto,
                run_name=run_name,
                output_path=output_path,
            )
            return audio_path

        except (RunNameInvalido, GPUOcupada, PipelineInternoFalhou) as e:
            raise SinteseFalhouError(f"Erro na síntese: {e}") from e

    async def validar_qualidade(
        self,
        audio_path: Path,
        texto_esperado: str,
        limite_wer: float | None = None,
        **kwargs
    ) -> tuple[float, bool]:
        """
        Valida qualidade do áudio via Faster-Whisper + WER.

        Args:
            audio_path: Caminho do áudio
            texto_esperado: Texto esperado
            limite_wer: Limite de WER para aprovação
            **kwargs: Ignorados

        Returns:
            Tupla (wer, aprovado)
        """
        if limite_wer is None:
            limite_wer = settings.wer_limite_aprovacao

        wer, palavras = await validar_audio(
            caminho_audio=audio_path,
            texto_esperado=texto_esperado,
            limite_wer=limite_wer,
        )

        aprovado = wer <= limite_wer
        return wer, aprovado

    def liberar_recursos(self) -> None:
        """
        Libera recursos (não há modelo local nesta engine).

        O pipeline Kokoro+Seed-VC roda em processo separado.
        """
        # Nenhum recurso local para liberar
        pass


# Singleton global
_engine: KokoroSeedVCEngine | None = None


def get_tts_engine() -> KokoroSeedVCEngine:
    """Retorna instância singleton do engine Kokoro+Seed-VC."""
    global _engine
    if _engine is None:
        _engine = KokoroSeedVCEngine()
    return _engine


def liberar_engine() -> None:
    """Libera engine singleton."""
    global _engine
    if _engine is not None:
        _engine.liberar_recursos()
        _engine = None
