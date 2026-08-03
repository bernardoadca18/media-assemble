"""
FASE 3 — Validação de áudio via Faster-Whisper + WER — NÃO implementado nesta base.
Ver guia de arquitetura, seção 3.3, para a especificação completa
(inclui a função de distância de Levenshtein e cálculo de WER).
"""
from pathlib import Path


async def validar_audio(caminho_audio: Path, texto_esperado: str, limite_wer: float = 0.05):
    raise NotImplementedError("Fase 3: implementar validação via Faster-Whisper.")
