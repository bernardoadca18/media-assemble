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
import gc
import logging
import shutil
from pathlib import Path

from services.trends.scraper import coletar_tendencias
from services.trends.normalizer import normalizar_tendencias
from services.ideation.agent import gerar_ideias
from services.scripting.writer_agent import gerar_roteiro
from db.models import salvar_ideias, salvar_roteiro, salvar_execucao
from utils.logger import set_video_id

logger = logging.getLogger("orchestrator")


def _verificar_memoria_disponivel() -> float:
    """
    Retorna memória disponível em GB.
    Usa psutil se disponível, caso contrário retorna valor alto (sem verificação).
    """
    try:
        import psutil
        memoria = psutil.virtual_memory()
        return memoria.available / (1024 ** 3)  # Converte para GB
    except ImportError:
        return 999.0  # psutil não disponível, assume memória infinita


def _limpar_cache_temporarios() -> None:
    """
    Limpa caches e diretórios temporários antigos.
    """
    temp_dirs = [
        Path("/tmp"),
        Path.cwd() / "temp",
    ]

    for temp_dir in temp_dirs:
        if temp_dir.exists():
            try:
                # Remove arquivos temporários antigos do projeto
                for arquivo in temp_dir.glob("timbre_var_*.wav"):
                    try:
                        arquivo.unlink(missing_ok=True)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("orchestrator.erro_limpar_temp", extra={"erro": str(e)})


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

    # Subfase 8.8 — Marcar ideia manual como usada
    if ideia.ideia_manual_id:
        from db.models import marcar_ideia_manual_usada
        await marcar_ideia_manual_usada(ideia.ideia_manual_id, video_id)
        logger.info(
            "roteirizacao.ideia_manual_marcada_usada",
            extra={
                "video_id": video_id,
                "ideia_manual_id": ideia.ideia_manual_id,
            }
        )

    logger.info(
        "roteirizacao.concluida",
        extra={
            "video_id": video_id,
            "total_cenas": len(roteiro.cenas),
            "duracao": roteiro.metadata.duracao_estimada_segundos,
        }
    )
    return roteiro


async def retomar_execucao_falha(video_id: str) -> dict | None:
    """
    Retoma uma execução falha a partir da etapa em que parou.

    Lê o roteiro persistido em dados.roteiros (quando disponível) e
    continua a partir da etapa que falhou.

    Args:
        video_id: ID do vídeo a ser retomado

    Returns:
        Dict com {sucesso: bool, roteiro: Roteiro, video_id: str}
        ou {sucesso: False, etapa: str, erro: str, video_id: str}
    """
    from db.models import buscar_execucao_falha, carregar_roteiro

    logger.info("pipeline.retomando_execucao", extra={"video_id": video_id})

    # Buscar execução falha
    execucao = await buscar_execucao_falha(video_id)
    if not execucao:
        logger.warning("pipeline.execucao_nao_encontrada", extra={"video_id": video_id})
        return {"sucesso": False, "etapa": "desconhecida", "erro": "Execução não encontrada", "video_id": video_id}

    etapa_atual = execucao["etapa_atual"]
    nicho = execucao["nicho"]

    logger.info(
        "pipeline.retome_encontrada",
        extra={"video_id": video_id, "etapa": etapa_atual, "nicho": nicho}
    )

    # Carregar roteiro se existir (para fases >= 2)
    roteiro = None
    if etapa_atual in ["roteirizacao", "audio", "assets", "renderizacao"]:
        roteiro = await carregar_roteiro(video_id)
        if not roteiro:
            logger.error(
                "pipeline.roteiro_nao_encontrado",
                extra={"video_id": video_id, "etapa": etapa_atual}
            )
            return {
                "sucesso": False,
                "etapa": etapa_atual,
                "erro": "Roteiro não encontrado no banco",
                "video_id": video_id
            }

    # Função auxiliar para registrar falha
    async def _registrar_falha(etapa: str, erro: Exception) -> dict:
        from db.models import salvar_execucao
        await salvar_execucao(
            video_id=video_id,
            nicho=nicho,
            etapa_atual=etapa,
            sucesso=False,
            motivo_falha=f"{type(erro).__name__}: {str(erro)}",
        )
        logger.error(
            f"pipeline.retomada.{etapa}.falhou",
            extra={
                "video_id": video_id,
                "nicho": nicho,
                "erro_tipo": type(erro).__name__,
                "erro_msg": str(erro),
            },
            exc_info=True,
        )
        return {"sucesso": False, "etapa": etapa, "erro": str(erro), "video_id": video_id}

    # Retomar a partir da etapa falha
    # Fase 1: Ideação - reinicia do zero (não há roteiro ainda)
    if etapa_atual == "ideacao":
        try:
            ideias = await rodar_etapa_ideacao(nicho)
            if not ideias:
                return {"sucesso": False, "etapa": "ideacao", "erro": "Nenhuma ideia gerada", "video_id": video_id}

            # Continua para Fase 2
            ideia_escolhida = ideias[0]
            roteiro = await rodar_etapa_roteirizacao(ideia=ideia_escolhida, nicho=nicho)
            video_id = roteiro.metadata.video_id
        except Exception as e:
            return await _registrar_falha("ideacao", e)

    # Fase 2: Roteirização - reinicia do zero se não tiver roteiro
    if etapa_atual == "roteirizacao":
        if not roteiro:
            # Precisa recomeçar da ideação
            logger.warning("pipeline.roteirizacao_sem_roteiro", extra={"video_id": video_id})
            return {
                "sucesso": False,
                "etapa": "roteirizacao",
                "erro": "Roteiro não encontrado - impossível retomar",
                "video_id": video_id
            }
        # Roteiro já existe, continua para próxima fase

    # Fase 3: Áudio - retoma a partir do roteiro existente
    if etapa_atual in ["audio", "assets", "renderizacao"]:
        try:
            from services.audio.pipeline_audio import gerar_audio_do_roteiro
            roteiro = await gerar_audio_do_roteiro(roteiro)
            await salvar_roteiro(roteiro)

            logger.info(
                "pipeline.retomada.audio_concluido",
                extra={"video_id": roteiro.metadata.video_id}
            )
        except Exception as e:
            return await _registrar_falha("audio", e)

    # Fase 4: Assets - retoma a partir do roteiro com áudio
    if etapa_atual in ["assets", "renderizacao"]:
        try:
            from services.visual.asset_resolver import resolver_assets_do_roteiro
            roteiro = await resolver_assets_do_roteiro(roteiro)
            await salvar_roteiro(roteiro)

            logger.info(
                "pipeline.retomada.assets_concluido",
                extra={"video_id": roteiro.metadata.video_id}
            )
        except Exception as e:
            return await _registrar_falha("assets", e)

    # Fase 5: Renderização - retoma a partir do roteiro completo
    if etapa_atual == "renderizacao":
        try:
            from services.render.remotion_bridge import renderizar_video
            video_path = await renderizar_video(roteiro)
            roteiro.metadata.video_final_path = str(video_path)
            await salvar_roteiro(roteiro)

            # Calcular WER médio
            cenas_com_wer = [c.wer_final for c in roteiro.cenas if c.wer_final is not None]
            wer_medio = sum(cenas_com_wer) / len(cenas_com_wer) if cenas_com_wer else None

            # Registrar sucesso
            from db.models import salvar_execucao
            await salvar_execucao(
                video_id=video_id,
                nicho=nicho,
                etapa_atual="renderizacao",
                sucesso=True,
                caminho_video_final=str(video_path),
                wer_medio=wer_medio,
            )

            logger.info(
                "pipeline.retomada.renderizacao_concluida",
                extra={"video_id": video_id, "video_final": str(video_path)}
            )

            return {"sucesso": True, "roteiro": roteiro, "video_id": video_id}
        except Exception as e:
            return await _registrar_falha("renderizacao", e)

    # Se chegou aqui, completou fases pendentes com sucesso
    return {"sucesso": True, "roteiro": roteiro, "video_id": video_id}


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
            motivo_falha=f"{type(erro).__name__}: {str(erro)}",
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
            motivo_falha="Nenhuma ideia gerada pelo LLM",
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
        set_video_id(video_id)  # Propagar video_id nos logs
    except Exception as e:
        return await _registrar_falha("roteirizacao", e)

    # --- VERIFICAÇÃO DE MEMÓRIA PRÉ-FASE 3 ---
    memoria_disponivel = _verificar_memoria_disponivel()
    logger.info("orchestrator.memoria_disponivel", extra={"memoria_gb": memoria_disponivel})
    if memoria_disponivel < 1.0:  # Menos de 1GB disponível
        logger.warning("orchestrator.memoria_baixa", extra={"memoria_gb": memoria_disponivel})
        # Tenta liberar memória antes de continuar
        _limpar_cache_temporarios()
        gc.collect()
        memoria_disponivel = _verificar_memoria_disponivel()
        if memoria_disponivel < 0.5:  # Menos de 500MB
            raise RuntimeError(f"Memória insuficiente para continuar: {memoria_disponivel:.2f}GB disponível")

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

    # --- LIMPEZA PÓS-FASE 3 ---
    # Modelos TTS e Whisper já foram liberados dentro de gerar_audio_do_roteiro
    logger.info("orchestrator.pos_audio_cleanup")
    _limpar_cache_temporarios()
    gc.collect()

    # --- VERIFICAÇÃO DE MEMÓRIA PRÉ-FASE 4 ---
    memoria_disponivel = _verificar_memoria_disponivel()
    logger.info("orchestrator.memoria_pre_assets", extra={"memoria_gb": memoria_disponivel})

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

        # --- Subfase 8.6: Metadata de publicação ---
        try:
            from services.metadata_generator import gerar_metadata_publicacao
            from pipeline.schemas import MetadataPublicacao

            metadata_dict = await gerar_metadata_publicacao(roteiro)
            roteiro.metadata.metadata_publicacao = MetadataPublicacao(**metadata_dict)
            await salvar_roteiro(roteiro)

            logger.info(
                "pipeline.metadata_gerada",
                extra={
                    "video_id": video_id,
                    "num_titulos": len(metadata_dict.get("titulos", [])),
                    "num_tags": len(metadata_dict.get("tags", [])),
                }
            )
        except Exception as e:
            logger.warning(
                "pipeline.metadata_falhou",
                extra={"video_id": video_id, "erro": str(e)},
                exc_info=True,
            )
            # Não falha o pipeline se metadata falhar

        # --- Subfase 8.5: Clipping automático para Shorts ---
        if _should_generate_shorts(nicho):
            try:
                shorts = await gerar_shorts_from_video_longo(roteiro)
                logger.info(
                    "pipeline.shorts_gerados",
                    extra={
                        "video_id_origem": video_id,
                        "num_shorts": len(shorts),
                    }
                )
            except Exception as e:
                logger.warning(
                    "pipeline.shorts_falhou",
                    extra={"video_id_origem": video_id, "erro": str(e)},
                    exc_info=True,
                )
                # Não falha o pipeline principal se shorts falharem

        return {"sucesso": True, "roteiro": roteiro, "video_id": video_id}

    except Exception as e:
        return await _registrar_falha("renderizacao", e, video_id)


def _should_generate_shorts(nicho: str) -> bool:
    """Verifica se deve gerar shorts automaticamente para o nicho."""
    import os
    from pipeline.nichos import obter_config_nicho

    try:
        # Verifica configuração global
        gerar_shorts = os.getenv("GERAR_SHORTS_AUTOMATICO", "false").lower() == "true"
        if not gerar_shorts:
            return False

        # Verifica se nicho tem prompt de short configurado
        config = obter_config_nicho(nicho)
        return bool(config.prompt_roteiro_short)
    except Exception:
        return False


async def gerar_shorts_from_video_longo(roteiro_longo, num_clips: int = 2) -> list:
    """
    Gera shorts a partir de um vídeo longo já finalizado.

    Args:
        roteiro_longo: Roteiro de vídeo longo com áudio e assets resolvidos
        num_clips: Número de clips a gerar (default: 2)

    Returns:
        Lista de roteiros de shorts gerados
    """
    from services.scripting.clip_selector import selecionar_clips, criar_roteiro_clip
    from services.render.remotion_bridge import renderizar_video_short
    from db.models import salvar_roteiro

    logger.info(
        "shorts.iniciando",
        extra={
            "video_id_origem": roteiro_longo.metadata.video_id,
            "num_clips": num_clips,
        }
    )

    # Selecionar trechos para clips
    clips_info = await selecionar_clips(roteiro_longo, num_clips=num_clips)

    shorts_gerados = []
    for clip_info in clips_info:
        try:
            # Criar roteiro derivado
            roteiro_short = criar_roteiro_clip(
                roteiro_longo=roteiro_longo,
                cena_inicio_id=clip_info["cena_inicio_id"],
                cena_fim_id=clip_info["cena_fim_id"],
                titulo_sugerido=clip_info["titulo_sugerido"],
            )

            # Salvar roteiro do short
            await salvar_roteiro(roteiro_short)

            # Renderizar short (formato vertical)
            video_path = await renderizar_video_short(roteiro_short)
            roteiro_short.metadata.video_final_path = str(video_path)
            await salvar_roteiro(roteiro_short)

            shorts_gerados.append(roteiro_short)

            logger.info(
                "shorts.clip_renderizado",
                extra={
                    "video_id_short": roteiro_short.metadata.video_id,
                    "video_origem": roteiro_longo.metadata.video_id,
                    "titulo": clip_info["titulo_sugerido"],
                }
            )

        except Exception as e:
            logger.warning(
                "shorts.clip_falhou",
                extra={
                    "video_origem": roteiro_longo.metadata.video_id,
                    "clip_info": clip_info,
                    "erro": str(e),
                },
                exc_info=True,
            )
            continue

    return shorts_gerados