"""
Lock global de GPU.

A RTX 2060 (12GB) é um recurso único e compartilhado por várias etapas do
pipeline (LLM local via LiteLLM, F5-TTS, Faster-Whisper). Este módulo garante
que apenas UMA tarefa que toca a GPU rode por vez, evitando estouro de VRAM
por concorrência.

Uso:
    async with gpu_task("f5-tts-cena-03"):
        ... código que usa a GPU ...
"""
import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("gpu_lock")

_gpu_semaphore = asyncio.Semaphore(1)
_gpu_locked = False  # Track se está em uso
_gpu_task_name = None  # Nome da tarefa atual


@asynccontextmanager
async def gpu_task(task_name: str):
    global _gpu_locked, _gpu_task_name
    logger.info("gpu_lock.waiting", extra={"task": task_name})
    async with _gpu_semaphore:
        _gpu_locked = True
        _gpu_task_name = task_name
        logger.info("gpu_lock.started", extra={"task": task_name})
        try:
            yield
        finally:
            _gpu_locked = False
            _gpu_task_name = None
            logger.info("gpu_lock.finished", extra={"task": task_name})


def gpu_status() -> dict:
    """
    Retorna status atual do GPU lock.

    Returns:
        dict com 'disponivel' (bool) e 'tarefa_atual' (str | None)
    """
    return {
        "disponivel": not _gpu_locked,
        "tarefa_atual": _gpu_task_name,
    }
