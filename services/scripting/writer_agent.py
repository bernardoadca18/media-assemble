"""
FASE 2 — Agente de Roteirização (NÃO implementado nesta base — escopo da Fase 2).

Deve receber uma `Ideia` (pipeline.schemas.Ideia) aprovada e retornar um
objeto `Roteiro` (pipeline.schemas.Roteiro) completo e validado, usando o
System Prompt já definido no guia de arquitetura (seção 5).
"""
from pipeline.schemas import Ideia, Roteiro


async def gerar_roteiro(ideia: Ideia) -> Roteiro:
    raise NotImplementedError("Fase 2: implementar geração de roteiro completo via LLM.")
