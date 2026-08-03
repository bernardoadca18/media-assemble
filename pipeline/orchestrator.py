"""
Orquestrador principal do pipeline.

Este módulo é o "maestro" — substitui o fluxo visual do n8n por um pipeline
Python explícito, com cada etapa isolada em services/. Nesta versão inicial
(base para a Fase 1), apenas a etapa de Tendências + Ideação está ativa; as
demais etapas são chamadas como stubs a serem implementados nas fases
seguintes (ver RELATORIO_FASES_DESENVOLVIMENTO.md).
"""
import asyncio
import logging

from services.trends.scraper import coletar_tendencias
from services.trends.normalizer import normalizar_tendencias
from services.ideation.agent import gerar_ideias
from db.models import salvar_ideias

logger = logging.getLogger("orchestrator")


async def rodar_etapa_ideacao(nicho: str) -> list:
    """
    Escopo da Fase 1: coleta -> normalização -> ideação -> persistência.
    Retorna a lista de ideias geradas e já salvas no banco.
    """
    tendencias_brutas = await coletar_tendencias(nicho)
    tendencias = await normalizar_tendencias(tendencias_brutas)

    ideias = await gerar_ideias(nicho=nicho, tendencias=tendencias)
    await salvar_ideias(ideias)

    logger.info("ideacao.concluida", extra={"nicho": nicho, "total_ideias": len(ideias)})
    return ideias


async def rodar_pipeline_completo(nicho: str):
    """
    Pipeline ponta-a-ponta. A partir da Fase 2 em diante, este método passa
    a encadear roteirização -> áudio -> assets -> render. Por enquanto,
    delega apenas à etapa de ideação (Fase 1).
    """
    ideias = await rodar_etapa_ideacao(nicho)

    # TODO (Fase 2): escolher 1 ideia e chamar services.scripting.writer_agent
    # TODO (Fase 3): gerar áudio via services.audio.pipeline_audio
    # TODO (Fase 4): resolver assets via services.visual.asset_resolver
    # TODO (Fase 5): renderizar via services.render.remotion_bridge

    return ideias


if __name__ == "__main__":
    from pipeline.config import settings

    for nicho in settings.nichos_lista:
        asyncio.run(rodar_pipeline_completo(nicho))
