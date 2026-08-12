"""
Cliente HTTP para o pipeline de voz Kokoro + Seed-VC.

Comunica-se com o serviço externo via API REST `/narrar` para gerar
áudio sintetizado com conversão de voz.
"""
import asyncio
import logging
import time
from pathlib import Path

import httpx

from pipeline.config import settings

logger = logging.getLogger("services.audio.voice_pipeline_client")


class VoicePipelineError(Exception):
    """Erro base do pipeline de voz."""
    pass


class RunNameInvalido(VoicePipelineError):
    """run_name não possui checkpoint treinado."""
    pass


class GPUOcupada(VoicePipelineError):
    """GPU em uso por outra requisição - retry com backoff."""
    pass


class PipelineInternoFalhou(VoicePipelineError):
    """Falha interna no serviço (Kokoro, Seed-VC, timeout)."""
    pass


class VoicePipelineClient:
    """
    Cliente HTTP para o endpoint /narrar do pipeline Kokoro+Seed-VC.

    Características:
    - Timeout generoso (5 min por cena)
    - Retry automático para código 409 (GPU ocupada)
    - Tratamento explícito de erros 400/409/500
    """

    def __init__(
        self,
        base_url: str | None = None,
        timeout: int | None = None,
        max_retries: int | None = None,
        retry_delay: float | None = None,
    ):
        self.base_url = base_url or settings.voice_pipeline_url
        self.timeout = timeout or settings.voice_pipeline_timeout
        self.max_retries = max_retries or settings.voice_pipeline_max_retries
        self.retry_delay = retry_delay or settings.voice_pipeline_retry_delay

    async def narrar(
        self,
        texto: str,
        run_name: str | None = None,
        output_path: Path | None = None,
    ) -> tuple[Path, float]:
        """
        Gera áudio narrado via pipeline Kokoro+Seed-VC.

        Args:
            texto: Texto a ser narrado
            run_name: Nome do checkpoint treinado (default: configuração global)
            output_path: Caminho para salvar o áudio (default: temp file)

        Returns:
            Tupla (caminho_audio, tempo_sintese_segundos)

        Raises:
            RunNameInvalido: run_name sem checkpoint treinado
            GPUOcupada: GPU ocupada após esgotar retries
            PipelineInternoFalhou: Falha interna no serviço
        """
        if not texto or not texto.strip():
            raise RunNameInvalido("Texto não pode estar vazio")

        run_name = run_name or settings.voice_pipeline_run_name_default

        logger.info(
            "voice_pipeline.narrando",
            extra={
                "texto_len": len(texto),
                "run_name": run_name,
                "base_url": self.base_url,
            }
        )

        start_time = time.time()

        # Retry loop para código 409
        for attempt in range(1, self.max_retries + 1):
            try:
                audio_path = await self._call_narrar_api(
                    texto=texto,
                    run_name=run_name,
                    output_path=output_path,
                )

                tempo_sintese = time.time() - start_time

                logger.info(
                    "voice_pipeline.concluido",
                    extra={
                        "tempo_sintese": tempo_sintese,
                        "tentativas": attempt,
                        "run_name": run_name,
                    }
                )

                return audio_path, tempo_sintese

            except GPUOcupada as e:
                if attempt < self.max_retries:
                    logger.warning(
                        "voice_pipeline.gpu_ocupada_retry",
                        extra={
                            "attempt": attempt,
                            "max_retries": self.max_retries,
                            "retry_delay": self.retry_delay,
                        }
                    )
                    await asyncio.sleep(self.retry_delay)
                else:
                    raise

            except (RunNameInvalido, PipelineInternoFalhou):
                raise

        raise RuntimeError("Não deveria chegar aqui")

    async def _call_narrar_api(
        self,
        texto: str,
        run_name: str,
        output_path: Path | None,
    ) -> Path:
        """
        Faz chamada HTTP para /narrar.

        Raises:
            RunNameInvalido: código 400
            GPUOcupada: código 409
            PipelineInternoFalhou: código 500 ou timeout
        """
        import tempfile

        url = f"{self.base_url}/narrar"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    url,
                    json={"texto": texto, "run_name": run_name},
                )

                # Tratamento por código de status
                if response.status_code == 200:
                    # Salva áudio recebido
                    if output_path is None:
                        output_path = Path(tempfile.mktemp(suffix=".wav", prefix="voice_pipeline_"))

                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(response.content)

                    logger.info(
                        "voice_pipeline.audio_salvo",
                        extra={"output_path": str(output_path)}
                    )

                    return output_path

                elif response.status_code == 400:
                    error_detail = response.json().get("detail", "Erro desconhecido")
                    raise RunNameInvalido(f"run_name inválido ou texto vazio: {error_detail}")

                elif response.status_code == 409:
                    raise GPUOcupada("GPU ocupada - faça retry com backoff")

                elif response.status_code == 500:
                    error_detail = response.json().get("detail", "Erro interno desconhecido")
                    raise PipelineInternoFalhou(f"Erro interno no pipeline: {error_detail}")

                else:
                    raise PipelineInternoFalhou(f"Status inesperado: {response.status_code}")

        except httpx.TimeoutException as e:
            logger.error(
                "voice_pipeline.timeout",
                extra={
                    "timeout": self.timeout,
                    "texto_len": len(texto),
                }
            )
            raise PipelineInternoFalhou(f"Timeout após {self.timeout}s") from e

        except httpx.RequestError as e:
            logger.error(
                "voice_pipeline.erro_rede",
                extra={"erro": str(e)}
            )
            raise PipelineInternoFalhou(f"Erro de rede: {e}") from e

    async def healthcheck(self) -> bool:
        """
        Verifica se o serviço de voz está saudável.

        Returns:
            True se saudável, False caso contrário
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return response.status_code == 200
        except Exception as e:
            logger.warning("voice_pipeline.healthcheck_falhou", extra={"erro": str(e)})
            return False


# Instância global (lazy)
_client: VoicePipelineClient | None = None


def get_voice_pipeline_client() -> VoicePipelineClient:
    """Retorna cliente singleton do pipeline de voz."""
    global _client
    if _client is None:
        _client = VoicePipelineClient()
    return _client
