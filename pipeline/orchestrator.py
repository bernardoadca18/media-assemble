"""
Orquestrador principal do pipeline.

Este módulo é o "maestro" — substitui o fluxo visual do n8n por um pipeline
Python explícito, com cada etapa isolada em services/.
- Fase 1 (Tendências + Ideação): implementada
- Fase 2 (Roteirização): implementada
- Fases 3-5: stubs a serem implementados (ver RELATORIO_FASES_DESENVOLVIMENTO.md)
"""
import asyncio
import logging

from services.trends.scraper import coletar_tendencias
from services.trends.normalizer import normalizar_tendencias
from services.ideation.agent import gerar_ideias
from services.scripting.writer_agent import gerar_roteiro
from db.models import salvar_ideias, salvar_roteiro

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


async def rodar_etapa_roteirizacao(ideia, nicho: str = "cultura_pop"):
    """
    Escopo da Fase 2: dado uma Ideia, gerar e persistir um Roteiro completo.
    Retorna o roteiro validado e salvo no banco.
    """
    roteiro = await gerar_roteiro(ideia=ideia, nicho=nicho)
    video_id = await salvar_roteiro(roteiro)

    logger.info(
        "roteirizacao.concluida",
        extra={
            "video_id": video_id,
            "total_cenas": len(roteiro.cenas),
            "duracao": roteiro.metadata.duracao_estimada_segundos,
        }
    )
    return roteiro


async def rodar_pipeline_completo(nicho: str):
    """
    Pipeline ponta-a-ponta.
    - Fase 1: coleta tendências -> gera 5 ideias
    - Fase 2: seleciona 1 ideia -> gera roteiro completo
    - Fase 3: gera áudio para cada cena -> valida via Whisper -> concatena
    - Fases 4-5: stubs (não implementados nesta fase)
    """
    # Fase 1: Ideação
    ideias = await rodar_etapa_ideacao(nicho)

    if not ideias:
        logger.warning("pipeline.sem_ideias", extra={"nicho": nicho})
        return None

    # Fase 2: Roteirização (usar a primeira ideia)
    ideia_escolhida = ideias[0]
    logger.info(
        "pipeline.ideia_selecionada",
        extra={"topico": ideia_escolhida.topico, "titulo": ideia_escolhida.titulo_sugerido}
    )

    roteiro = await rodar_etapa_roteirizacao(ideia=ideia_escolhida, nicho=nicho)

    # Fase 3: Geração de áudio
    from services.audio.pipeline_audio import gerar_audio_do_roteiro
    roteiro = await gerar_audio_do_roteiro(roteiro)

    # Persiste novamente o roteiro agora com os campos de áudio preenchidos
    # (audio_path/palavras_transcritas por cena, audio_final_path no
    # metadata) — sem isso, todo o trabalho de TTS/validação feito acima
    # ficaria apenas em memória e se perderia caso o processo seja
    # interrompido antes da Fase 5.
    await salvar_roteiro(roteiro)

    logger.info(
        "pipeline.audio_concluido",
        extra={
            "video_id": roteiro.metadata.video_id,
            "audio_final": roteiro.metadata.audio_final_path,
        }
    )

    # Fase 4: Resolução de assets visuais
    from services.visual.asset_resolver import resolver_assets_do_roteiro
    roteiro = await resolver_assets_do_roteiro(roteiro)

    # Persiste novamente o roteiro agora com os assets resolvidos
    await salvar_roteiro(roteiro)

    logger.info(
        "pipeline.assets_concluido",
        extra={
            "video_id": roteiro.metadata.video_id,
            "cenas_com_asset": sum(1 for c in roteiro.cenas if c.asset_resolvido_path),
            "cenas_sem_asset": sum(1 for c in roteiro.cenas if not c.asset_resolvido_path),
        }
    )

    # TODO (Fase 5): renderizar via services.render.remotion_bridge

    return roteiro