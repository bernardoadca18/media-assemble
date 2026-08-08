"""
Seleção de clips a partir de vídeos longos para Shorts.
Subfase 8.5 — Suporte a Shorts (clipping).

Dado um Roteiro longo já finalizado (áudio + assets resolvidos),
usa LLM para identificar 2-4 trechos contíguos autocontidos e
gera Roteiros derivados formato="short" reaproveitando assets.
"""
import json
import logging
import uuid
from typing import TypeVar

from pipeline.config import settings
from pipeline.schemas import Roteiro, Cena, MetadataRoteiro
from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.scripting.clip_selector")

T = TypeVar("T")

PROMPT_SELECAO_CLIPS = """\
Contexto: Você é um Editor de Vídeo especialista em criar Shorts virais a partir
de conteúdo longo existente.

DADOS DE ENTRADA:
- Roteiro completo do vídeo longo (duração: {duracao_total}s)
- Título: {titulo}
- Cenas disponíveis com seus timestamps e textos de locução

{cenas_json}

OBJETIVO:
Identificar exatamente {num_clips} trechos contíguos e autocontidos que podem
ser transformados em Shorts independentes (25-58s cada).

CRITÉRIOS DE SELEÇÃO:
1. Trechos com início forte (gancho imediato nos primeiros 1-2s)
2. Uma ideia central clara e completa
3. Fechamento que induza replay ou continuação
4. Evitar spoilers de momentos-chave do vídeo longo
5. Preferir trechos com alto potencial viral

PARA CADA CLIP SELECIONADO:
- Indique cena_inicio e cena_fim (IDs das cenas)
- Proponha um título viral específico para o Short
- Justifique brevemente por que esse trecho funciona como Short

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "clips": [
    {{
      "cena_inicio_id": int,
      "cena_fim_id": int,
      "titulo_sugerido": "string",
      "justificativa": "string"
    }}
  ]
}}
"""


def _limpar_resposta_json(texto_bruto: str) -> str:
    """Remove blocos markdown e limpa a resposta do LLM."""
    texto = texto_bruto.strip()
    if texto.startswith("```json"):
        texto = texto[7:]
    elif texto.startswith("```"):
        texto = texto[3:]
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()


async def selecionar_clips(
    roteiro_longo: Roteiro,
    num_clips: int = 2,
) -> list[dict]:
    """
    Usa LLM para selecionar trechos de um vídeo longo para Shorts.

    Args:
        roteiro_longo: Roteiro completo de vídeo longo já finalizado
        num_clips: Número de clips a selecionar (default: 2)

    Returns:
        Lista de dicts com cena_inicio_id, cena_fim_id, titulo_sugerido

    Raises:
        RuntimeError: Se falhar na seleção
    """
    # Preparar dados das cenas
    cenas_data = []
    for cena in roteiro_longo.cenas:
        cenas_data.append({
            "cena_id": cena.cena_id,
            "texto_locucao": cena.texto_locucao,
            "duracao": cena.duracao_estimada_segundos,
            "asset_resolvido": cena.asset_resolvido_path is not None,
        })

    cenas_json = json.dumps(cenas_data, indent=2, ensure_ascii=False)

    prompt = PROMPT_SELECAO_CLIPS.format(
        duracao_total=roteiro_longo.metadata.duracao_estimada_segundos,
        titulo=roteiro_longo.metadata.titulo_sugerido,
        cenas_json=cenas_json,
        num_clips=num_clips,
    )

    try:
        resposta_bruta = await complete_cloud(
            prompt,
            model=settings.cloud_model_roteiro,
            operacao="clip_selection",
            nicho=roteiro_longo.metadata.nicho,
            video_id=roteiro_longo.metadata.video_id,
        )
        texto_limpo = _limpar_resposta_json(resposta_bruta)
        dados = json.loads(texto_limpo)

        if "clips" not in dados or not isinstance(dados["clips"], list):
            raise ValueError("Resposta não contém lista de clips")

        logger.info(
            "clip_selector.sucesso",
            extra={
                "video_id_origem": roteiro_longo.metadata.video_id,
                "num_clips": len(dados["clips"]),
            }
        )

        return dados["clips"]

    except json.JSONDecodeError as e:
        logger.error(
            "clip_selector.json_invalido",
            extra={"erro": str(e), "resposta": texto_limpo[:500]}
        )
        raise RuntimeError(f"JSON inválido na seleção de clips: {e}") from e
    except Exception as e:
        logger.error(
            "clip_selector.erro",
            extra={"erro": str(e)}
        )
        raise RuntimeError(f"Erro na seleção de clips: {e}") from e


def criar_roteiro_clip(
    roteiro_longo: Roteiro,
    cena_inicio_id: int,
    cena_fim_id: int,
    titulo_sugerido: str,
) -> Roteiro:
    """
    Cria um Roteiro derivado (formato="short") a partir de trecho de vídeo longo.

    Args:
        roteiro_longo: Roteiro original (longo)
        cena_inicio_id: ID da primeira cena do clip
        cena_fim_id: ID da última cena do clip
        titulo_sugerido: Título para o Short

    Returns:
        Novo Roteiro com formato="short" e video_origem_id vinculando ao original
    """
    # Encontrar cenas do intervalo
    cenas_clip = [
        cena
        for cena in roteiro_longo.cenas
        if cena_inicio_id <= cena.cena_id <= cena_fim_id
    ]

    if not cenas_clip:
        raise ValueError(
            f"Nenhuma cena encontrada entre {cena_inicio_id} e {cena_fim_id}"
        )

    # Calcular duração do clip
    duracao_clip = sum(c.duracao_estimada_segundos for c in cenas_clip)

    # Validar duração para Short
    if not (25.0 <= duracao_clip <= 58.0):
        logger.warning(
            "criar_roteiro_clip.duracao_invalida",
            extra={
                "duracao": duracao_clip,
                "cena_inicio": cena_inicio_id,
                "cena_fim": cena_fim_id,
            }
        )
        raise ValueError(
            f"Clip tem {duracao_clip}s. Shorts devem ter entre 25s e 58s."
        )

    # Criar novo video_id para o clip
    video_id_short = f"{roteiro_longo.metadata.video_id}_clip_{uuid.uuid4().hex[:4]}"

    # Reordenar cenas (sequencial a partir de 1)
    for i, cena in enumerate(cenas_clip):
        cena.cena_id = i + 1
        cena.ordem = i + 1

    # Criar metadata do short
    metadata_short = MetadataRoteiro(
        video_id=video_id_short,
        nicho=roteiro_longo.metadata.nicho,
        titulo_sugerido=titulo_sugerido,
        duracao_estimada_segundos=duracao_clip,
        trilha_fundo=roteiro_longo.metadata.trilha_fundo,
        volume_trilha_fundo=roteiro_longo.metadata.volume_trilha_fundo,
        formato="short",
        video_origem_id=roteiro_longo.metadata.video_id,
        # Herdar audio_final_path se disponível (será recortado posteriormente)
        audio_final_path=roteiro_longo.metadata.audio_final_path,
    )

    # Criar roteiro derivado
    roteiro_short = Roteiro(
        metadata=metadata_short,
        cenas=cenas_clip,
    )

    logger.info(
        "criar_roteiro_clip.sucesso",
        extra={
            "video_id_short": video_id_short,
            "video_origem": roteiro_longo.metadata.video_id,
            "duracao": duracao_clip,
            "num_cenas": len(cenas_clip),
        }
    )

    return roteiro_short
