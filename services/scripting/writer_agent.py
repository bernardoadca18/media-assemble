"""
FASE 2 — Agente de Roteirização.

Recebe uma `Ideia` (pipeline.schemas.Ideia) aprovada e retorna um
objeto `Roteiro` (pipeline.schemas.Roteiro) completo e validado.

Estratégia:
- System prompt editorial com gancho nos primeiros segundos
- Cenas de 3-8 segundos, uma ideia por cena
- Variação de tipo de animação entre cenas consecutivas
- Uso moderado de texto_destaque_tela
- Retry com correção em caso de falha de validação Pydantic
"""
import json
import logging
import uuid
from typing import TypeVar

from pipeline.config import settings
from pipeline.schemas import (
    Ideia,
    Roteiro,
    Cena,
    MetadataRoteiro,
    Midia,
    EfeitosVisuais,
    Overlays,
    TipoAsset,
    AnimacaoImagem,
)
from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.scripting.writer_agent")

T = TypeVar("T")

# System prompt de roteirização editorial
PROMPT_SISTEMA_ROTEIRO = """\
Contexto: Você é um Roteirista Senior de vídeos "faceless" para YouTube,
especialista em cultura pop, lore de animes, filmes, séries e jogos.

DADOS DE ENTRADA:
- Tópico: {topico}
- Título sugerido: {titulo}
- Descrição do ângulo: {descricao}
- Duração-alvo: {duracao_alvo} segundos

OBJETIVO:
Criar um roteiro completo em JSON com cenas de 3-8 segundos cada, totalizando
aproximadamente {duracao_alvo} segundos. O roteiro deve ser estruturado para
prender a atenção nos primeiros 3 segundos (gancho forte).

DIRETRIZES EDITORIAIS OBRIGATÓRIAS:

1. GANCHO INICIAL (cena 1):
   - Primeira frase deve ser impactante, gerar curiosidade ou apresentar
     uma revelação imediata.
   - Ex: "O que poucos sabem é que...", "Existe um segredo que...", etc.

2. ESTRUTURA DAS CENAS:
   - Cada cena = uma ideia principal, clara e direta.
   - Duração: entre 3 e 8 segundos por cena.
   - Texto de locução: frases curtas, linguagem coloquial mas informativa.
   - Não repetir a mesma animação mais de 2 vezes seguidas.

3. ANIMAÇÕES DISPONÍVEIS (varie entre elas):
   - ken_burns_zoom_in: zoom lento para dentro (dramático, revelação)
   - ken_burns_zoom_out: zoom lento para fora (contexto, panorama)
   - pan_lateral: movimento lateral (transição, comparação)

4. TIPOS DE ASSET:
   - imagem: para ilustrações, conceitos, personagens estáticos
   - video: para clipes, trechos animados, cenas em movimento
   - Prefira "imagem" para maior controle visual; use "video" com moderação.

5. TEXTOS EM TELA (texto_destaque_tela):
   - Use COM MODERAÇÃO: no máximo 1 a cada 3 cenas.
   - Apenas para ênfase em nomes, conceitos-chave ou revelações impactantes.
   - Não repita o que está sendo dito na locução — complemente ou destaque.

6. KEYWORDS DE BUSCA:
   - Seja específico: "Naruto Uzumaki modo sábio" é melhor que "Naruto".
   - Inclua termos em português e inglês quando relevante.
   - Forneça fallback_query genérico caso a busca específica falhe.

7. TRILHA DE FUNDO:
   - Escolha entre: "epica", "suspense", "medieval", "emocionante", "acao".
   - Volume padrão: 0.15 (não alterar).

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "metadata": {{
    "video_id": "string único (UUID)",
    "nicho": "cultura_pop",
    "titulo_sugerido": "string",
    "duracao_estimada_segundos": float,
    "trilha_fundo": "string",
    "volume_trilha_fundo": 0.15
  }},
  "cenas": [
    {{
      "cena_id": int (sequencial, iniciando em 1),
      "ordem": int (sequencial, iniciando em 1),
      "texto_locucao": "string (texto falado nesta cena)",
      "duracao_estimada_segundos": float (entre 3.0 e 8.0),
      "midia": {{
        "tipo_asset_preferencial": "imagem" ou "video",
        "keywords_busca": ["keyword1", "keyword2"],
        "fallback_query": "string (busca genérica de backup)",
        "duracao_minima": float (mesmo valor da duração da cena)
      }},
      "efeitos_visuais": {{
        "animacao_imagem": "ken_burns_zoom_in" ou "ken_burns_zoom_out" ou "pan_lateral",
        "transicao_saida": "fade",
        "duracao_transicao_segundos": 0.5
      }},
      "overlays": {{
        "exibir_legenda": true,
        "texto_destaque_tela": "string ou null"
      }}
    }}
  ]
}}

VALIDAÇÕES OBRIGATÓRIAS:
- total de cenas: entre 15 e 40 (para duração de ~3 minutos)
- duração de cada cena: entre 3.0 e 8.0 segundos
- não repetir animacao_imagem mais que 2x consecutivas
- texto_destaque_tela: máximo em 1/3 das cenas
"""

# Prompt de correção para retry
PROMPT_CORRECAO = """\
O JSON gerado anteriormente falhou na validação. Aqui está o erro específico:

{erro_validacao}

Por favor, corrija APENAS os pontos indicados no erro acima, mantendo o resto do roteiro igual.
Retorne o JSON completo corrigido, no mesmo formato.
"""


def _limpar_resposta_json(texto_bruto: str) -> str:
    """Remove blocos markdown e limpa a resposta do LLM."""
    texto = texto_bruto.strip()
    # Remove blocos de código markdown
    if texto.startswith("```json"):
        texto = texto[7:]
    elif texto.startswith("```"):
        texto = texto[3:]
    if texto.endswith("```"):
        texto = texto[:-3]
    return texto.strip()


def _validar_regras_negocio(roteiro: Roteiro) -> list[str]:
    """Valida regras de negócio específicas além do schema Pydantic."""
    erros = []

    # Validar número de cenas
    if len(roteiro.cenas) < 10:
        erros.append(f"Poucas cenas ({len(roteiro.cenas)}). Mínimo esperado: 10.")
    if len(roteiro.cenas) > 50:
        erros.append(f"Muitas cenas ({len(roteiro.cenas)}). Máximo esperado: 50.")

    # Validar duração de cada cena
    for i, cena in enumerate(roteiro.cenas):
        if cena.duracao_estimada_segundos < 3.0:
            erros.append(
                f"Cena {cena.cena_id} muito curta ({cena.duracao_estimada_segundos}s). "
                f"Mínimo: 3.0 segundos."
            )
        if cena.duracao_estimada_segundos > 8.0:
            erros.append(
                f"Cena {cena.cena_id} muito longa ({cena.duracao_estimada_segundos}s). "
                f"Máximo: 8.0 segundos."
            )

    # Validar animações consecutivas (não mais que 2x seguidas)
    animacoes_consecutivas = []
    for cena in roteiro.cenas:
        anim = cena.efeitos_visuais.animacao_imagem
        animacoes_consecutivas.append(anim)

    for i in range(len(animacoes_consecutivas) - 2):
        a1, a2, a3 = animacoes_consecutivas[i], animacoes_consecutivas[i+1], animacoes_consecutivas[i+2]
        if a1 == a2 == a3:
            erros.append(
                f"Animação '{a1}' repetida 3 vezes consecutivas nas cenas "
                f"{roteiro.cenas[i].cena_id}, {roteiro.cenas[i+1].cena_id}, {roteiro.cenas[i+2].cena_id}. "
                f"Máximo permitido: 2 repetições."
            )

    # Validar moderação de texto_destaque_tela
    cenas_com_destaque = sum(1 for c in roteiro.cenas if c.overlays.texto_destaque_tela)
    limite_destaque = len(roteiro.cenas) // 3
    if cenas_com_destaque > limite_destaque:
        erros.append(
            f"Texto_destaque_tela usado em {cenas_com_destaque} cenas. "
            f"Máximo permitido: {limite_destaque} (1/3 do total)."
        )

    return erros


async def _tentar_gerar_roteiro(
    prompt: str,
    tentativa: int,
    max_tentativas: int,
) -> Roteiro:
    """
    Tenta gerar e validar um roteiro.
    Levanta exceção se esgotar tentativas.
    """
    resposta_bruta = await complete_cloud(prompt, model=settings.cloud_model_roteiro)
    texto_limpo = _limpar_resposta_json(resposta_bruta)

    try:
        dados = json.loads(texto_limpo)
        roteiro = Roteiro.model_validate(dados)
    except json.JSONDecodeError as e:
        logger.warning(
            "gerar_roteiro.json_invalido",
            extra={"tentativa": tentativa, "erro": str(e), "resposta": texto_limpo[:500]}
        )
        raise ValueError(f"JSON inválido: {e}") from e
    except Exception as e:
        logger.warning(
            "gerar_roteiro.validacao_falhou",
            extra={"tentativa": tentativa, "erro": str(e)}
        )
        raise ValueError(f"Validação Pydantic falhou: {e}") from e

    # Validar regras de negócio
    erros_negocio = _validar_regras_negocio(roteiro)
    if erros_negocio:
        logger.warning(
            "gerar_roteiro.regras_negocio_falharam",
            extra={"tentativa": tentativa, "erros": erros_negocio}
        )
        raise ValueError("Regras de negócio violadas:\n" + "\n".join(erros_negocio))

    # A duração declarada pelo LLM em metadata é apenas uma estimativa
    # informada por ele mesmo — pode divergir da soma real das cenas.
    # Recalculamos aqui para que o valor usado pelas Fases 3 e 5 (áudio e
    # render, que dependem dessa duração para sincronização) seja sempre
    # exato, e não uma aproximação do modelo.
    roteiro.metadata.duracao_estimada_segundos = sum(
        cena.duracao_estimada_segundos for cena in roteiro.cenas
    )

    logger.info(
        "gerar_roteiro.sucesso",
        extra={
            "tentativa": tentativa,
            "total_cenas": len(roteiro.cenas),
            "duracao_total": roteiro.metadata.duracao_estimada_segundos,
        }
    )

    return roteiro


async def gerar_roteiro(
    ideia: Ideia,
    duracao_alvo_segundos: float = 180.0,
    max_tentativas: int = 3,
    nicho: str = "cultura_pop",
) -> Roteiro:
    """
    Gera um roteiro completo a partir de uma Ideia.

    Args:
        ideia: Ideia validada da Fase 1
        duracao_alvo_segundos: Duração alvo do vídeo (default: 180s)
        max_tentativas: Máximo de tentativas em caso de falha (default: 3)
        nicho: Nicho do vídeo (default: cultura_pop)

    Returns:
        Roteiro validado e pronto para as Fases 3 e 4

    Raises:
        RuntimeError: Se esgotar todas as tentativas sem sucesso
    """
    # Gerar video_id único
    video_id = str(uuid.uuid4())[:8]

    # Montar prompt inicial
    prompt_inicial = PROMPT_SISTEMA_ROTEIRO.format(
        topico=ideia.topico,
        titulo=ideia.titulo_sugerido,
        descricao=ideia.descricao_breve,
        duracao_alvo=int(duracao_alvo_segundos),
    )

    # Adicionar video_id e nicho ao prompt
    prompt_inicial += f'\n\nGere o video_id como: "{video_id}"\nUse nicho: "{nicho}"'

    ultimo_erro = None

    for tentativa in range(1, max_tentativas + 1):
        try:
            if tentativa == 1:
                prompt = prompt_inicial
            else:
                # Retry com prompt de correção
                prompt = PROMPT_CORRECAO.format(
                    erro_validacao=str(ultimo_erro)
                ) + "\n\n" + prompt_inicial

            roteiro = await _tentar_gerar_roteiro(prompt, tentativa, max_tentativas)

            # Garantir que video_id e nicho estão corretos
            roteiro.metadata.video_id = video_id
            roteiro.metadata.nicho = nicho
            roteiro.metadata.titulo_sugerido = ideia.titulo_sugerido

            return roteiro

        except ValueError as e:
            ultimo_erro = e
            logger.warning(
                "gerar_roteiro.tentativa_falhou",
                extra={"tentativa": tentativa, "erro": str(e)}
            )
            continue

    # Esgotou tentativas
    erro_final = f"Falha ao gerar roteiro após {max_tentativas} tentativas. Último erro: {ultimo_erro}"
    logger.error(
        "gerar_roteiro.tentativas_esgotadas",
        extra={"max_tentativas": max_tentativas, "ultimo_erro": str(ultimo_erro)}
    )
    raise RuntimeError(erro_final)