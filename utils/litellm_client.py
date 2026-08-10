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

# Configuração global do LiteLLM: remove parâmetros não suportados pelo backend
# Isso é necessário para modelos Ollama que não suportam encoding_format
litellm.drop_params = True
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
        # Quando usando proxy, adiciona prefixo openai/ para evitar detecção automática de provider
        if not modelo_alvo.startswith("openai/"):
            modelo_alvo = f"openai/{modelo_alvo}"
        logger.debug(f"Usando proxy LiteLLM: {api_base} com modelo {modelo_alvo}")

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
    model: str = "ollama-embed",
    operacao: str = "embedding",
    nicho: str | None = None,
    video_id: str | None = None,
) -> list[float]:
    """
    Gera embedding para um texto usando modelo de embedding via LiteLLM.

    Usa modelo de embedding padrão ollama-embed ou
    modelo configurado via variável de ambiente.

    Args:
        text: Texto para gerar embedding
        model: Modelo de embedding (padrão: ollama-embed)
        operacao: Nome da operação para rastreamento de custos
        nicho: Nicho relacionado (para rastreamento)
        video_id: ID do vídeo (para rastreamento)

    Returns:
        Lista de floats representando o embedding (dimensão depende do modelo)
    """
    # Usar httpx diretamente para evitar parâmetros extras do LiteLLM
    if settings.litellm_base_url and settings.litellm_master_key:
        import httpx

        api_base = settings.litellm_base_url.rstrip("/")
        api_key = settings.litellm_master_key

        logger.debug(f"Usando proxy LiteLLM para embedding: {api_base} com modelo {model}")

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{api_base}/v1/embeddings",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "input": text,
                    },
                )
                response.raise_for_status()
                data = response.json()

                # Extrair embedding da resposta
                if "data" in data and len(data["data"]) > 0:
                    return data["data"][0]["embedding"]

                logger.error(f"Resposta inesperada do proxy: {data}")
                return None

        except Exception as e:
            logger.error(f"Erro ao chamar proxy LiteLLM para embedding: {e}")
            raise

    # Fallback para LiteLLM direto (sem proxy)
    try:
        resposta = await litellm.aembedding(
            model=model,
            input=[text],
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
        # A resposta do LiteLLM tem estrutura: EmbeddingResponse(data=[Embedding(embedding=[...])])
        if resposta.data and len(resposta.data) > 0:
            embedding_obj = resposta.data[0]
            # Pode ser objeto Embedding ou dict
            if hasattr(embedding_obj, "embedding"):
                return embedding_obj.embedding
            elif isinstance(embedding_obj, dict):
                return embedding_obj.get("embedding")
        logger.error(f"Estrutura de resposta inesperada: {resposta}")
        return None

    except Exception as e:
        logger.error(
            "litellm.erro_embedding",
            extra={"erro": str(e), "tipo": type(e).__name__, "modelo": model}
        )
        import traceback
        logger.error(f"Traceback embedding: {traceback.format_exc()}")
        raise
