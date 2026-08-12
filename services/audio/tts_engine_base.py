"""
Interface abstrata para engines de TTS.

Define o contrato que qualquer engine de síntese de voz deve seguir,
permitindo troca de implementação sem modificar o pipeline principal.
"""
from abc import ABC, abstractmethod
from pathlib import Path


class TTSEngine(ABC):
    """
    Interface abstrata para engines de síntese de voz.

    Qualquer engine (F5-TTS, Kokoro+Seed-VC, etc.) deve implementar
    estes métodos para ser compatível com o pipeline.
    """

    @abstractmethod
    async def sintetizar(
        self,
        texto: str,
        output_path: Path,
        **kwargs
    ) -> Path:
        """
        Sintetiza áudio a partir de texto.

        Args:
            texto: Texto a ser sintetizado
            output_path: Caminho para salvar o áudio
            **kwargs: Parâmetros específicos da engine (seed, voice_profile, etc.)

        Returns:
            Path do arquivo de áudio gerado

        Raises:
            TTSError: Se a síntese falhar
        """
        pass

    @abstractmethod
    async def validar_qualidade(
        self,
        audio_path: Path,
        texto_esperado: str,
        **kwargs
    ) -> tuple[float, bool]:
        """
        Valida a qualidade do áudio gerado.

        Args:
            audio_path: Caminho do áudio
            texto_esperado: Texto que deveria estar no áudio
            **kwargs: Parâmetros de validação (limite_wer, etc.)

        Returns:
            Tupla (score_qualidade, aprovado)
            - score_qualidade: WER, similaridade, ou outra métrica
            - aprovado: True se passou no critério de qualidade
        """
        pass

    @abstractmethod
    def liberar_recursos(self) -> None:
        """
        Libera recursos GPU/RAM utilizados pela engine.

        Deve ser chamado após concluir o processamento de todas as cenas.
        """
        pass


class TTSError(Exception):
    """Erro base para engines de TTS."""
    pass


class SinteseFalhouError(TTSError):
    """Erro durante a síntese de áudio."""
    pass


class ValidacaoFalhouError(TTSError):
    """Erro durante a validação de qualidade."""
    pass
