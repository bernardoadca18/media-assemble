"""
Orquestrador principal do pipeline.

Este módulo é o "maestro" — substitui o fluxo visual do n8n por um pipeline
Python explícito, com cada etapa isolada em services/.
- Fase 1 (Tendências + Ideação): implementada
- Fase 2 (Roteirização): implementada
- Fase 3 (Áudio): implementada
- Fase 4 (Assets Visuais): implementada
- Fase 5 (Renderização/Remotion): implementada
"""
import asyncio
import logging

from services.trends.scraper import coletar_tendencias
from services.trends.normalizer import normalizar_tendencias
from services.ideation.agent import gerar_ideias
from services.scripting.writer_agent import gerar_roteiro
from db.models import salvar_ideias, salvar_roteiro, salvar_execucao

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


async def rodar_pipeline_completo(nicho: str) -> dict | None:
    """
    Pipeline ponta-a-ponta.
    - Fase 1: coleta tendências -> gera 5 ideias
    - Fase 2: seleciona 1 ideia -> gera roteiro completo
    - Fase 3: gera áudio para cada cena -> valida via Whisper -> concatena
    - Fase 4: resolve assets visuais (banco local + fallback Pexels)
    - Fase 5: renderiza o vídeo final via Remotion (subprocess)

    Retorna o roteiro se sucesso, ou um dict com {'sucesso': False, 'etapa': str, 'erro': str, 'video_id': str | None}
    em caso de falha. Nunca propaga exceção para fora — garante que o scheduler continue agendando.
    """
    video_id: str | None = None

    # Função auxiliar para registrar falha e retornar estrutura padronizada
    async def _registrar_falha(etapa: str, erro: Exception, video_id_local: str | None = None) -> dict:
        await salvar_execucao(
            video_id=video_id_local,
            nicho=nicho,
            etapa_atual=etapa,
            sucesso=False,
        )
        logger.error(
            f"pipeline.{etapa}.falhou",
            extra={
                "nicho": nicho,
                "video_id": video_id_local,
                "erro_tipo": type(erro).__name__,
                "erro_msg": str(erro),
            },
            exc_info=True,
        )
        return {"sucesso": False, "etapa": etapa, "erro": str(erro), "video_id": video_id_local}

    # --- Fase 1: Ideação ---
    try:
        ideias = await rodar_etapa_ideacao(nicho)
    except Exception as e:
        return await _registrar_falha("ideacao", e)

    if not ideias:
        logger.warning("pipeline.sem_ideias", extra={"nicho": nicho})
        await salvar_execucao(
            video_id=None,
            nicho=nicho,
            etapa_atual="ideacao",
            sucesso=False,
        )
        return {"sucesso": False, "etapa": "ideacao", "erro": "Nenhuma ideia gerada", "video_id": None}

    # --- Fase 2: Roteirização ---
    ideia_escolhida = ideias[0]
    logger.info(
        "pipeline.ideia_selecionada",
        extra={"topico": ideia_escolhida.topico, "titulo": ideia_escolhida.titulo_sugerido}
    )

    try:
        roteiro = await rodar_etapa_roteirizacao(ideia=ideia_escolhida, nicho=nicho)
        video_id = roteiro.metadata.video_id
    except Exception as e:
        return await _registrar_falha("roteirizacao", e)

    # --- Fase 3: Geração de áudio ---
    try:
        from services.audio.pipeline_audio import gerar_audio_do_roteiro
        roteiro = await gerar_audio_do_roteiro(roteiro)

        # Persiste roteiro com campos de áudio preenchidos
        await salvar_roteiro(roteiro)

        logger.info(
            "pipeline.audio_concluido",
            extra={
                "video_id": roteiro.metadata.video_id,
                "audio_final": roteiro.metadata.audio_final_path,
            }
        )
    except Exception as e:
        return await _registrar_falha("audio", e, video_id)

    # --- Fase 4: Resolução de assets visuais ---
    try:
        from services.visual.asset_resolver import resolver_assets_do_roteiro
        roteiro = await resolver_assets_do_roteiro(roteiro)

        # Persiste roteiro com assets resolvidos
        await salvar_roteiro(roteiro)

        logger.info(
            "pipeline.assets_concluido",
            extra={
                "video_id": roteiro.metadata.video_id,
                "cenas_com_asset": sum(1 for c in roteiro.cenas if c.asset_resolvido_path),
                "cenas_sem_asset": sum(1 for c in roteiro.cenas if not c.asset_resolvido_path),
            }
        )
    except Exception as e:
        return await _registrar_falha("assets", e, video_id)

    # --- Fase 5: Renderização via Remotion ---
    try:
        from services.render.remotion_bridge import renderizar_video
        video_path = await renderizar_video(roteiro)

        # Atualizar roteiro com caminho do vídeo
        roteiro.metadata.video_final_path = str(video_path)

        # Persistir roteiro final com caminho do vídeo
        await salvar_roteiro(roteiro)

        # Calcular WER médio das cenas
        cenas_com_wer = [c.wer_final for c in roteiro.cenas if c.wer_final is not None]
        wer_medio = sum(cenas_com_wer) / len(cenas_com_wer) if cenas_com_wer else None

        # Registrar sucesso final
        await salvar_execucao(
            video_id=video_id,
            nicho=nicho,
            etapa_atual="renderizacao",
            sucesso=True,
            caminho_video_final=str(video_path),
            wer_medio=wer_medio,
        )

        logger.info(
            "pipeline.renderizacao_concluida",
            extra={
                "video_id": roteiro.metadata.video_id,
                "video_final": roteiro.metadata.video_final_path,
                "wer_medio": wer_medio,
            }
        )

        return {"sucesso": True, "roteiro": roteiro, "video_id": video_id}

    except Exception as e:
        return await _registrar_falha("renderizacao", e, video_id)