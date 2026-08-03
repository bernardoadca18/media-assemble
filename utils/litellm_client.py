"""
Cliente único para o LiteLLM, usado por todo o pipeline.

Centraliza a decisão de qual modelo usar (local via Ollama/vLLM vs. nuvem)
para que os services/ nunca precisem saber detalhes de qual provedor está
por trás — apenas chamam `complete_local(...)` ou `complete_cloud(...)`.

IMPORTANTE: chamadas a modelos LOCAIS tocam a GPU e devem sempre passar
pelo `gpu_task` (pipeline.gpu_lock). Chamadas a modelos em NUVEM não
precisam do lock, pois não consomem a VRAM local.
"""
import logging

import litellm

from pipeline.config import settings
from pipeline.gpu_lock import gpu_task

logger = logging.getLogger("utils.litellm_client")


async def complete_local(prompt: str, **kwargs) -> str:
    """
    Usa o modelo local configurado (ex: Qwen via Ollama) para tarefas leves
    como normalização de tendências. Protegido por gpu_lock.
    """
    async with gpu_task(f"llm-local-{settings.local_model_name}"):
        resposta = await litellm.acompletion(
            model=settings.local_model_name,
            api_base=settings.local_model_base_url,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
    return resposta.choices[0].message.content


async def complete_cloud(prompt: str, model: str | None = None, **kwargs) -> str:
    """
    Usa um modelo em nuvem (Gemini/OpenAI/Claude) para tarefas que exigem
    mais qualidade/raciocínio, como ideação e roteirização. Não usa gpu_lock.
    """
    modelo_alvo = model or settings.cloud_model_ideacao
    resposta = await litellm.acompletion(
        model=modelo_alvo,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    return resposta.choices[0].message.content
