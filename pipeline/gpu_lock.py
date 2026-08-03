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


@asynccontextmanager
async def gpu_task(task_name: str):
    logger.info("gpu_lock.waiting", extra={"task": task_name})
    async with _gpu_semaphore:
        logger.info("gpu_lock.started", extra={"task": task_name})
        try:
            yield
        finally:
            logger.info("gpu_lock.finished", extra={"task": task_name})
