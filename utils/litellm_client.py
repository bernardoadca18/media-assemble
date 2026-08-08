"""
Cliente único para o LiteLLM, usado por todo o pipeline.

Centraliza a decisão de qual modelo usar (local via Ollama/vLLM vs. nuvem)
para que os services/ nunca precisem saber detalhes de qual provedor está
por trás — apenas chamam `complete_local(...)` ou `complete_cloud(...)`.

IMPORTANTE: chamadas a modelos LOCAIS tocam a GPU e devem sempre passar
pelo `gpu_task` (pipeline.gpu_lock). Chamadas a modelos em NUVEM não
precisam do lock, pois não consomem a VRAM local.

Inclui rastreamento de custos via utils/cost_tracker.py.
"""
import logging
from typing import Any

import litellm
from litellm.exceptions import (
    Timeout,
    RateLimitError,
    ServiceUnavailableError,
    APIConnectionError,
)

from pipeline.config import settings
from pipeline.gpu_lock import gpu_task
from utils.retry import ErroPermanente, ErroTransitorio, com_retry

logger = logging.getLogger("utils.litellm_client")


def _registrar_uso(response: Any, modelo: str, operacao: str, nicho: str | None = None, video_id: str | None = None) -> None:
    """Extrai tokens da resposta e registra uso para custos."""
    try:
        from utils.cost_tracker import registrar_chamada

        usage = getattr(response, "usage", None)
        if usage:
            registrar_chamada(
                operacao=operacao,
                modelo=modelo,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                nicho=nicho,
                video_id=video_id,
            )
    except Exception as e:
        logger.warning(
            "litellm_client.erro_registrar_custo",
            extra={"erro": str(e)}
        )


async def _complete_local_interno(prompt: str, **kwargs) -> Any:
    """Implementação interna sem retry, extraída para testes. Retorna resposta completa."""
    async with gpu_task(f"llm-local-{settings.local_model_name}"):
        resposta = await litellm.acompletion(
            model=settings.local_model_name,
            api_base=settings.local_model_base_url,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
    return resposta


async def complete_local(
    prompt: str,
    operacao: str = "llm.local",
    nicho: str | None = None,
    video_id: str | None = None,
    **kwargs
) -> str:
    """
    Usa o modelo local configurado (ex: Qwen via Ollama) para tarefas leves
    como normalização de tendências. Protegido por gpu_lock.

    Retry apenas para erros de timeout/conexão. Erros de validação
    (schema, JSON) falham imediatamente.
    """
    async def _chamada():
        try:
            return await _complete_local_interno(prompt, **kwargs)
        except (Timeout, APIConnectionError, ServiceUnavailableError) as e:
            logger.warning(
                "litellm.erro_transitorio_local",
                extra={"erro": str(e), "tipo": type(e).__name__}
            )
            raise ErroTransitorio(str(e)) from e
        except Exception as e:
            # Erros de autenticação, contexto excedido, etc.
            logger.error(
                "litellm.erro_permanente_local",
                extra={"erro": str(e), "tipo": type(e).__name__}
            )
            raise ErroPermanente(str(e)) from e

    resposta = await com_retry(
        _chamada,
        nome_operacao=operacao,
        max_tentativas=3
    )
    _registrar_uso(resposta, settings.local_model_name, operacao, nicho, video_id)
    return resposta.choices[0].message.content


async def _complete_cloud_interno(prompt: str, model: str | None = None, **kwargs) -> Any:
    """Implementação interna sem retry, extraída para testes. Retorna resposta completa."""
    modelo_alvo = model or settings.cloud_model_ideacao

    # Configurar proxy LiteLLM se disponível
    api_base = None
    api_key = None
    if settings.litellm_base_url and settings.litellm_master_key:
        api_base = settings.litellm_base_url
        api_key = settings.litellm_master_key
        logger.debug(f"Usando proxy LiteLLM: {api_base}")

    resposta = await litellm.acompletion(
        model=modelo_alvo,
        messages=[{"role": "user", "content": prompt}],
        api_base=api_base,
        api_key=api_key,
        **kwargs,
    )
    return resposta


async def complete_cloud(
    prompt: str,
    model: str | None = None,
    operacao: str = "llm.cloud",
    nicho: str | None = None,
    video_id: str | None = None,
    **kwargs
) -> str:
    """
    Usa um modelo em nuvem (Gemini/OpenAI/Claude) para tarefas que exigem
    mais qualidade/raciocínio, como ideação e roteirização. Não usa gpu_lock.

    Retry para erros de timeout, rate limit, conexão e indisponibilidade.
    Erros de autenticação, contexto excedido, etc., falham imediatamente.
    """
    async def _chamada():
        try:
            return await _complete_cloud_interno(prompt, model, **kwargs)
        except (Timeout, RateLimitError, APIConnectionError, ServiceUnavailableError) as e:
            logger.warning(
                "litellm.erro_transitorio_cloud",
                extra={"erro": str(e), "tipo": type(e).__name__}
            )
            raise ErroTransitorio(str(e)) from e
        except Exception as e:
            logger.error(
                "litellm.erro_permanente_cloud",
                extra={"erro": str(e), "tipo": type(e).__name__}
            )
            raise ErroPermanente(str(e)) from e

    resposta = await com_retry(
        _chamada,
        nome_operacao=operacao,
        max_tentativas=3
    )
    modelo_alvo = model or settings.cloud_model_ideacao
    _registrar_uso(resposta, modelo_alvo, operacao, nicho, video_id)
    return resposta.choices[0].message.content


async def generate_embedding(
    text: str,
    model: str = "text-embedding-3-small",
    operacao: str = "embedding",
    nicho: str | None = None,
    video_id: str | None = None,
) -> list[float]:
    """
    Gera embedding para um texto usando modelo de embedding via LiteLLM.

    Usa modelo de embedding padrão text-embedding-3-small (OpenAI) ou
    modelo configurado via variável de ambiente.

    Args:
        text: Texto para gerar embedding
        model: Modelo de embedding (padrão: text-embedding-3-small)
        operacao: Nome da operação para rastreamento de custos
        nicho: Nicho relacionado (para rastreamento)
        video_id: ID do vídeo (para rastreamento)

    Returns:
        Lista de floats representando o embedding (dimensão depende do modelo)
    """
    # Configurar proxy LiteLLM se disponível
    api_base = None
    api_key = None
    if settings.litellm_base_url and settings.litellm_master_key:
        api_base = settings.litellm_base_url
        api_key = settings.litellm_master_key

    try:
        resposta = await litellm.aembedding(
            model=model,
            input=[text],
            api_base=api_base,
            api_key=api_key,
        )

        # Registrar uso para custos
        usage = getattr(resposta, "usage", None)
        if usage:
            from utils.cost_tracker import registrar_chamada
            registrar_chamada(
                operacao=operacao,
                modelo=model,
                input_tokens=usage.prompt_tokens,
                output_tokens=0,  # Embeddings não têm output_tokens
                nicho=nicho,
                video_id=video_id,
            )

        # Retornar o embedding (primeiro da lista, pois passamos um único input)
        return resposta.data[0]["embedding"]

    except Exception as e:
        logger.error(
            "litellm.erro_embedding",
            extra={"erro": str(e), "tipo": type(e).__name__}
        )
        raise
