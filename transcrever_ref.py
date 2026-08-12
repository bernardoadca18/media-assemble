#!/usr/bin/env python3
"""Transcreve áudio de referência para obter o texto."""
import sys
from pathlib import Path

try:
    from faster_whisper import WhisperModel
except ImportError:
    print("Erro: faster-whisper não está instalado")
    sys.exit(1)

audio_path = Path("data/voz_referencia/audio_ref.wav")
if not audio_path.exists():
    print(f"Erro: Arquivo não encontrado: {audio_path}")
    sys.exit(1)

print("Carregando modelo Whisper...")
model = WhisperModel('medium', device='cuda', compute_type='float16')

print(f"Transcrevendo {audio_path}...")
segments, info = model.transcribe(str(audio_path), language='pt')

texto = ' '.join([seg.text.strip() for seg in segments])

print("\n" + "="*60)
print("TEXTO TRANSCRITO DO ÁUDIO DE REFERÊNCIA:")
print("="*60)
print(texto)
print("="*60)
print(f"\nDuração: {info.duration:.2f}s")
print(f"\nCopie este texto para a variável F5_TTS_REF_TEXT no .env")
