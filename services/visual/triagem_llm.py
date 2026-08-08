"""
Triagem de assets por LLM.

Antes de aceitar definitivamente um asset candidato de qualquer fonte de fallback,
envia a imagem (ou sua descrição/metadata) e o contexto da cena ao LLM para
confirmação de relevância/adequação.

NOTA: Esta etapa avalia relevância e adequação de conteúdo, NÃO licenciamento.
O licenciamento já está garantido pela fonte escolhida (Pexels, Pixabay, Unsplash,
Wikimedia Commons).
"""
import json
import logging
from typing import Optional

from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.visual.triagem_llm")


async def triar_asset_llm(
    descricao_asset: str,
    contexto_cena: str,
    keywords: list[str],
    tipo_asset: str = "imagem",
) -> bool:
    """
    Usa LLM para avaliar se um asset é relevante/adequado para a cena.

    Args:
        descricao_asset: Descrição ou metadata do asset (retornada pela API)
        contexto_cena: Contexto da cena do roteiro
        keywords: Keywords usadas na busca do asset
        tipo_asset: "imagem" ou "video"

    Returns:
        True se o asset é adequado, False se deve ser rejeitado
    """
    prompt = f"""Você é um assistente especializado em curadoria de conteúdo visual para vídeos.

Sua tarefa é avaliar se um asset ({tipo_asset}) é relevante e adequado para uma cena específica de um vídeo.

**Contexto da cena:**
{contexto_cena}

**Keywords de busca:**
{", ".join(keywords)}

**Descrição/metadata do asset:**
{descricao_asset}

**Critérios de avaliação:**
1. Relevância temática: O asset está relacionado ao tema da cena?
2. Adequação de conteúdo: O conteúdo é apropriado e profissional?
3. Coerência visual: O asset faz sentido no contexto das keywords?

**IMPORTANTE:**
- Você está avaliando apenas RELEVÂNCIA e ADEQUAÇÃO de conteúdo
- Questões de licenciamento/direitos autorais NÃO são sua responsabilidade
- Seja criterioso mas não excessivamente conservador

Responda em JSON com a seguinte estrutura:
{{
    "aprovado": true ou false,
    "motivo": "breve explicação da decisão (1 frase)"
}}

Responda APENAS com o JSON, sem texto adicional."""

    try:
        resposta = await complete_cloud(prompt)

        # Parsear resposta JSON
        resposta_limpa = resposta.strip()
        if resposta_limpa.startswith("```json"):
            resposta_limpa = resposta_limpa[7:]
        if resposta_limpa.startswith("```"):
            resposta_limpa = resposta_limpa[3:]
        if resposta_limpa.endswith("```"):
            resposta_limpa = resposta_limpa[:-3]
        resposta_limpa = resposta_limpa.strip()

        resultado = json.loads(resposta_limpa)
        aprovado = resultado.get("aprovado", False)
        motivo = resultado.get("motivo", "")

        logger.info(
            "triagem_llm.resultado",
            extra={
                "aprovado": aprovado,
                "motivo": motivo,
                "keywords": keywords[:3],  # Primeiras 3 para log
            }
        )

        return aprovado

    except json.JSONDecodeError as e:
        logger.error(
            "triagem_llm.erro_json",
            extra={"erro": str(e), "resposta": resposta[:100] if resposta else None}
        )
        # Em caso de erro de parsing, assume aprovado (não bloqueia pipeline)
        return True

    except Exception as e:
        logger.error(
            "triagem_llm.erro_inesperado",
            extra={"erro": str(e)}
        )
        # Em caso de erro, assume aprovado (não bloqueia pipeline)
        return True
