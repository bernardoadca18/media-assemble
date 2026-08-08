"""
FASE 1 — Agente de Ideação.

Equivalente direto ao nó "Message a model1" do fluxo n8n original: recebe as
tendências normalizadas + o histórico de títulos recentes, monta o prompt
editorial completo e solicita ao LLM exatamente 5 ideias de vídeo, já
validadas via Pydantic.

Suporta múltiplos nichos com prompts personalizados via pipeline/nichos.py.
"""
import json
import logging
import os

from pipeline.schemas import Ideia, RespostaIdeacao
from pipeline.nichos import obter_config_nicho
from services.ideation.rag_client import buscar_titulos_recentes, checar_duplicidade_semantica
from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.ideation.agent")

# Limite de tentativas de substituição quando detecta duplicidade
LIMITE_TENTATIVAS_SUBSTITUICAO = int(os.getenv("LIMITE_TENTATIVAS_SUBSTITUICAO", "3"))


def _parsear_resposta(texto_bruto: str) -> RespostaIdeacao:
    texto_limpo = texto_bruto.replace("```json", "").replace("```", "").strip()
    dados = json.loads(texto_limpo)
    return RespostaIdeacao.model_validate(dados)


async def _solicitar_substituicao_ideia(
    nicho: str,
    titulo_rejeitado: str,
    motivo_rejeicao: str,
) -> Ideia | None:
    """
    Solicita ao LLM uma nova ideia para substituir uma rejeitada por duplicidade.

    Args:
        nicho: Nicho do canal
        titulo_rejeitado: Título que foi rejeitado
        motivo_rejeicao: Motivo da rejeição (para contexto do LLM)

    Returns:
        Nova ideia ou None se falhar
    """
    try:
        config = obter_config_nicho(nicho)

        prompt = f"""Uma ideia de vídeo foi rejeitada por duplicidade semântica.

**Ideia rejeitada:** {titulo_rejeitado}
**Motivo:** {motivo_rejeicao}

Por favor, sugira EXATAMENTE UMA nova ideia de vídeo para o nicho "{nicho}" que seja diferente da rejeitada.

Retorne APENAS um objeto JSON no formato:
{{"topico": "...", "titulo_sugerido": "...", "descricao_breve": "..."}}

Contexto do nicho: {config.descricao}
{f'Diretrizes adicionais: {config.prompt_roteiro_adicional}' if config.prompt_roteiro_adicional else ''}"""

        resposta_bruta = await complete_cloud(
            prompt=prompt,
            operacao="ideacao_substituicao",
            nicho=nicho,
        )

        # Parsear resposta como ideia única (remover markdown se presente)
        texto_limpo = resposta_bruta.replace("```json", "").replace("```", "").strip()
        resposta_json = json.loads(texto_limpo)
        ideia = Ideia(**resposta_json)
        ideia.nicho = nicho
        logger.info(
            "substituicao_ideia.sucesso",
            extra={
                "titulo_rejeitado": titulo_rejeitado,
                "novo_titulo": ideia.titulo_sugerido,
                "nicho": nicho,
            }
        )
        return ideia

    except Exception as e:
        logger.error(
            "substituicao_ideia.erro",
            extra={
                "titulo_rejeitado": titulo_rejeitado,
                "nicho": nicho,
                "erro": str(e),
            }
        )
        return None


async def gerar_ideias(nicho: str, tendencias: list[str]):
    # Obtém configuração específica do nicho
    config = obter_config_nicho(nicho)

    # ========================================================================
    # IDEIAS MANUAIS (Subfase 8.8)
    # ========================================================================
    # Buscar ideias manuais pendentes do nicho
    from db.models import buscar_ideias_manuais_pendentes
    ideias_manuais = await buscar_ideias_manuais_pendentes(nicho)

    # Separar por prioridade
    ideias_alta_prioridade = [i for i in ideias_manuais if i["prioridade"] == "alta"]
    ideias_prioridade_normal = [i for i in ideias_manuais if i["prioridade"] == "normal"]

    logger.info(
        "gerar_ideias.ideias_manuais_encontradas",
        extra={
            "nicho": nicho,
            "total_pendentes": len(ideias_manuais),
            "alta_prioridade": len(ideias_alta_prioridade),
            "prioridade_normal": len(ideias_prioridade_normal),
        }
    )

    historico = await buscar_titulos_recentes(nicho)
    historico_texto = (
        ", ".join(historico)
        if historico
        else "Nenhum vídeo publicado ainda. O canal está começando do zero, "
        "então você tem total liberdade com os temas fornecidos."
    )

    # Adicionar ideias de prioridade normal como contexto adicional no prompt
    contexto_ideias_manuais = ""
    if ideias_prioridade_normal:
        contexto_ideias_manuais = "\n\n**IDÉIAS MANUAIS DO USUÁRIO (considerar no lote):**\n"
        for ideia in ideias_prioridade_normal:
            contexto_ideias_manuais += f"- {ideia['titulo_sugerido']}"
            if ideia.get('descricao_breve'):
                contexto_ideias_manuais += f" — {ideia['descricao_breve']}"
            contexto_ideias_manuais += "\n"

    prompt = config.prompt_ideacao.format(
        tendencias=", ".join(tendencias) if tendencias else "Nenhuma tendência específica enviada.",
        historico=historico_texto,
    )

    # Adicionar contexto de ideias manuais ao prompt
    if contexto_ideias_manuais:
        prompt += contexto_ideias_manuais

    resposta_bruta = await complete_cloud(
        prompt,
        operacao="ideacao",
        nicho=nicho,
    )

    try:
        resposta = _parsear_resposta(resposta_bruta)
    except Exception as e:
        logger.error("gerar_ideias.parse_falhou", extra={"erro": str(e), "resposta": resposta_bruta})
        raise

    # O LLM não gera o campo `nicho` (não faz parte do prompt de saída);
    # atribuímos programaticamente aqui para que a persistência e as
    # consultas de histórico por nicho funcionem corretamente quando mais
    # de um nicho estiver ativo (ver NICHOS_ATIVOS no .env).
    for ideia in resposta.ideias:
        ideia.nicho = nicho

    # ========================================================================
    # SUBSTITUIÇÃO POR IDEIAS MANUAIS DE ALTA PRIORIDADE (Subfase 8.8)
    # ========================================================================
    # Se houver ideias manuais de alta prioridade, substituir as últimas
    # ideias geradas pelo LLM (sujeito à checagem de duplicidade)
    ideias_geradas_llm = resposta.ideias.copy()
    ideias_finais_antes_duplicidade = []

    for i, ideia_alta in enumerate(ideias_alta_prioridade):
        if i >= len(ideias_geradas_llm):
            break  # Não temos mais vagas para substituir

        # Criar objeto Ideia a partir da ideia manual
        ideia_manual = Ideia(
            topico=ideia_alta["titulo_sugerido"][:50],  # Derivar do título
            titulo_sugerido=ideia_alta["titulo_sugerido"],
            descricao_breve=ideia_alta.get("descricao_breve") or "Ideia manual do usuário",
            justificativa="Ideia injetada manualmente pelo usuário (alta prioridade)",
            potencial_viral=8.0,  # Default para ideias manuais
            nicho=nicho,
            ideia_manual_id=ideia_alta["id"],  # Flag para rastrear origem
        )

        # Substituir a última ideia do LLM pela ideia manual
        ideia_substituida = ideias_geradas_llm.pop()
        ideias_finais_antes_duplicidade.append(ideia_manual)

        logger.info(
            "gerar_ideias.ideia_manual_substituida",
            extra={
                "ideia_manual_id": ideia_alta["id"],
                "titulo": ideia_alta["titulo_sugerido"],
                "substituiu": ideia_substituida.titulo_sugerido,
                "nicho": nicho,
            }
        )

    # Adicionar ideias restantes do LLM
    ideias_finais_antes_duplicidade.extend(ideias_geradas_llm)

    # Usar lista combinada (ideias manuais + LLM) para checagem de duplicidade
    resposta.ideias = ideias_finais_antes_duplicidade

    # ========================================================================
    # CHECAGEM DE DUPLICIDADE SEMÂNTICA (Subfase 8.2)
    # ========================================================================
    # Para cada ideia, verificar se já existe título semanticamente similar.
    # Se detectar duplicata, tentar substituir via LLM até o limite de tentativas.
    ideias_finais = []
    for i, ideia in enumerate(resposta.ideias):
        tentativas = 0
        ideia_atual = ideia
        substituida_com_sucesso = False

        while tentativas < LIMITE_TENTATIVAS_SUBSTITUICAO:
            # Verificar duplicidade
            eh_duplicata = await checar_duplicidade_semantica(
                titulo_candidato=ideia_atual.titulo_sugerido,
                nicho=nicho,
            )

            if not eh_duplicata:
                # Ideia aprovada — adicionar à lista final
                ideias_finais.append(ideia_atual)
                substituida_com_sucesso = True
                break

            # Detectou duplicata — tentar substituir
            logger.warning(
                "gerar_ideias.duplicata_detectada",
                extra={
                    "indice": i,
                    "titulo": ideia_atual.titulo_sugerido,
                    "tentativa": tentativas + 1,
                    "limite": LIMITE_TENTATIVAS_SUBSTITUICAO,
                    "nicho": nicho,
                }
            )

            # Solicitar nova ideia ao LLM
            nova_ideia = await _solicitar_substituicao_ideia(
                nicho=nicho,
                titulo_rejeitado=ideia_atual.titulo_sugerido,
                motivo_rejeicao="já existe um vídeo semanticamente muito próximo a este tema",
            )

            if nova_ideia is None:
                # Falha ao obter substituição — parar tentativas
                logger.error(
                    "gerar_ideias.falha_substituicao",
                    extra={"titulo": ideia_atual.titulo_sugerido, "tentativa": tentativas + 1}
                )
                break

            ideia_atual = nova_ideia
            tentativas += 1

        # Se não conseguiu substituir com sucesso, manter ideia com flag de revisão
        if not substituida_com_sucesso:
            logger.warning(
                "gerar_ideias.sem_substituicao_valida",
                extra={
                    "titulo_original": ideia.titulo_sugerido,
                    "titulo_final": ideia_atual.titulo_sugerido,
                    "tentativas": tentativas,
                    "nicho": nicho,
                }
            )
            ideia_atual.requer_revisao_manual = True
            ideia_atual.motivo_revisao = (
                f"Não foi possível gerar substituição única após {tentativas} tentativa(s). "
                f"Último título candidato: '{ideia_atual.titulo_sugerido}'"
            )
            ideias_finais.append(ideia_atual)

    logger.info(
        "gerar_ideias.concluido",
        extra={
            "nicho": nicho,
            "total_ideias": len(ideias_finais),
            "ideias_requerem_revisao": sum(1 for i in ideias_finais if i.requer_revisao_manual),
        }
    )

    return ideias_finais