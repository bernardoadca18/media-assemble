"""
FASE 3 — Motor de TTS (F5-TTS) — NÃO implementado nesta base.
Ver guia de arquitetura, seção 3.2, para a especificação completa.
"""
from pathlib import Path


async def gerar_audio_cena(texto: str, saida: Path, seed: int | None = None) -> Path:
    raise NotImplementedError("Fase 3: implementar wrapper do F5-TTS com gpu_lock.")
