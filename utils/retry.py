"""
Utilitários de retry com backoff exponencial.

Fornece decoradores e funções para lidar com falhas transitórias
em chamadas externas (APIs, modelos em nuvem, etc).
"""
import logging
from typing import TypeVar

from tenacity import (
    AsyncRetrying,
    RetryError,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger("utils.retry")

T = TypeVar("T")

# Configuração padrão de retry
MAX_TENTATIVAS_PADRAO = 3
MULTIPLICADOR_BACKOFF = 1
TEMPO_ESPERA_MIN = 2  # segundos
TEMPO_ESPERA_MAX = 10  # segundos


class ErroTransitorio(Exception):
    """Marca erros que devem ter retry (timeout, conexão, rate limit)."""
    pass


class ErroPermanente(Exception):
    """Marca erros que NÃO devem ter retry (validação, autenticação, negócio)."""
    pass


async def com_retry(
    func_coro,
    *args,
    max_tentativas: int = MAX_TENTATIVAS_PADRAO,
    nome_operacao: str = "operacao",
    **kwargs
) -> T:
    """
    Executa uma coroutine com retry e backoff exponencial.

    Args:
        func_coro: Função assíncrona a ser executada
        *args: Argumentos posicionais para a função
        max_tentativas: Número máximo de tentativas
        nome_operacao: Nome da operação para logs
        **kwargs: Argumentos nomeados para a função

    Returns:
        Resultado da função

    Raises:
        RetryError: Se esgotar tentativas em erro transitório
        ErroPermanente: Se a função levantar erro permanente
    """
    try:
        async for tentativa in AsyncRetrying(
            stop=stop_after_attempt(max_tentativas),
            wait=wait_exponential(
                multiplier=MULTIPLICADOR_BACKOFF,
                min=TEMPO_ESPERA_MIN,
                max=TEMPO_ESPERA_MAX
            ),
            retry=retry_if_exception_type(ErroTransitorio),
            reraise=True,
        ):
            with tentativa:
                logger.debug(
                    f"{nome_operacao}.tentativa",
                    extra={"tentativa": tentativa.retry_state.attempt_number}
                )
                return await func_coro(*args, **kwargs)
    except RetryError as e:
        logger.error(
            f"{nome_operacao}.retry_esgotado",
            extra={
                "tentativas": max_tentativas,
                "erro": str(e.last_attempt.exception())
            }
        )
        raise
    except ErroPermanente as e:
        logger.error(
            f"{nome_operacao}.erro_permanente",
            extra={"erro": str(e)}
        )
        raise
