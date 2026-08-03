"""
FASE 3 — Concatenação/mixagem de áudio via FFmpeg — NÃO implementado nesta base.
Ver guia de arquitetura, seção 3.5.
"""
from pathlib import Path


async def concatenar_audios(cenas: list[dict], dir_temp: Path) -> str:
    raise NotImplementedError("Fase 3: implementar concatenação via FFmpeg concat demuxer.")
