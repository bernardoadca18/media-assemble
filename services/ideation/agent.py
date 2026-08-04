"""
FASE 1 — Agente de Ideação.

Equivalente direto ao nó "Message a model1" do fluxo n8n original: recebe as
tendências normalizadas + o histórico de títulos recentes, monta o prompt
editorial completo (ver PROMPT_SISTEMA abaixo, migrado 1:1 do fluxo n8n) e
solicita ao LLM exatamente 5 ideias de vídeo, já validadas via Pydantic.
"""
import json
import logging

from pipeline.schemas import RespostaIdeacao
from services.ideation.rag_client import buscar_titulos_recentes
from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.ideation.agent")

# Prompt migrado do nó "Message a model1" do Scrapper.json original.
# Mantido como referência editorial validada — ajustar conforme necessário,
# mas preservar a lógica de distribuição das 5 ideias (anime / filme-série /
# jogo / 2x evergreen), que já é testada e aprovada editorialmente.
PROMPT_SISTEMA = """\
Contexto: Você é um Master Copywriter e Estrategista de Conteúdo do YouTube,
especialista em canais "Faceless" de Cultura Pop, Nerd e "Lore" profunda.

DADOS DE ENTRADA:
- Tendências em Alta nesta semana: {tendencias}
- Histórico de vídeos JÁ PUBLICADOS (NÃO repita estes temas):
{historico}

OBJETIVO:
Criar exatamente 5 ideias de vídeos altamente virais e "clicáveis", baseadas
nos dados de entrada e na linha editorial do canal.

DIRETRIZES EDITORIAIS (OBRIGATÓRIO):
1. Títulos sempre no formato de explicações definitivas ou listas
   categorizadas (ex: "Todos os X de Y Explicados", "Os N Elementos mais
   Sombrios de Y").
2. Tom: pode usar adjetivos fortes (Sombrio, Brutal, Trágico, Épico,
   Fascinante), cobrindo terror, mistério, redenção, rivalidades, lore.
3. Foco 100% em Lore — ignore esportes e jogos competitivos sem narrativa.

DISTRIBUIÇÃO DAS 5 IDEIAS:
- Ideia 1 (Anime): obrigatoriamente um anime presente nas tendências.
- Ideia 2 (Filme/Série): obrigatoriamente uma obra presente nas tendências.
- Ideia 3 (Jogo): um jogo das tendências, ou um jogo atemporal de lore
  profunda (Elden Ring, Dark Souls, God of War) se não houver jogo nas
  tendências.
- Ideias 4 e 5 (Evergreen): temas atemporais e gerais de cultura pop/ficção.

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "ideias": [
    {{
      "topico": "Nome da Obra ou Tema Geral",
      "titulo_sugerido": "Título viral seguindo a estrutura exigida",
      "descricao_breve": "Resumo do ângulo específico / qual Lore será explicada"
    }}
  ]
}}
"""


def _parsear_resposta(texto_bruto: str) -> RespostaIdeacao:
    texto_limpo = texto_bruto.replace("```json", "").replace("```", "").strip()
    dados = json.loads(texto_limpo)
    return RespostaIdeacao.model_validate(dados)


async def gerar_ideias(nicho: str, tendencias: list[str]):
    historico = await buscar_titulos_recentes(nicho)
    historico_texto = (
        ", ".join(historico)
        if historico
        else "Nenhum vídeo publicado ainda. O canal está começando do zero, "
        "então você tem total liberdade com os temas fornecidos."
    )

    prompt = PROMPT_SISTEMA.format(
        tendencias=", ".join(tendencias) if tendencias else "Nenhuma tendência específica enviada.",
        historico=historico_texto,
    )

    resposta_bruta = await complete_cloud(prompt)

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

    return resposta.ideias