"""
Geração de metadata de publicação (SEO assistido).
Subfase 8.6 — Metadata de publicação.

Gera via LLM e persiste junto ao Roteiro:
- Título otimizado (2-3 variações)
- Descrição com capítulos derivados das cenas
- Tags relevantes
- Sugestão de playlist por nicho

Disponível via CLI e API HTTP.
"""
import json
import logging
from typing import TypeVar

from pipeline.config import settings
from pipeline.schemas import Roteiro
from utils.litellm_client import complete_cloud

logger = logging.getLogger("services.metadata_generator")

T = TypeVar("T")

PROMPT_METADATA = """\
Contexto: Você é um Especialista em SEO para YouTube, focado em vídeos "faceless"
de alta performance.

DADOS DE ENTRADA:
- Título original: {titulo_original}
- Nicho: {nicho}
- Formato: {formato}
- Duração: {duracao:.0f} segundos
- Cenas do roteiro (para extrair capítulos):
{cenas_resumo}

OBJETIVO:
Gerar metadata otimizada para publicação manual no YouTube, incluindo:
1. Títulos virais (2-3 variações com diferentes ângulos)
2. Descrição completa com capítulos timestampados
3. Tags relevantes (máximo 15)
4. Sugestão de playlist

DIRETRIZES DE SEO:
1. TÍTULOS:
   - Primeiras 60 chars são cruciais (visíveis no search)
   - Use números, perguntas ou revelações
   - Evite clickbait excessivo (mantenha promessa real)
   - Variação 1: Foco em curiosidade/mistério
   - Variação 2: Foco em lista/explicação
   - Variação 3: Foco em resultado/benefício

2. DESCRIÇÃO:
   - Primeira linha: hook que complementa o título
   - Capítulos com timestamps derivados das cenas
   - Call-to-action para inscrição
   - Palavras-chave naturais no texto

3. TAGS:
   - Mix de tags específicas e amplas
   - Incluir termos em português e inglês quando relevante
   - Máximo 500 chars total (YouTube limit)

4. PLAYLIST:
   - Sugerir playlist existente por nicho ou criar nova
   - Nome descritivo da playlist

FORMATO DE SAÍDA ESTRITO (APENAS JSON VÁLIDO, SEM MARKDOWN):
{{
  "titulos": [
    "Título variação 1 (foco em curiosidade)",
    "Título variação 2 (foco em lista)",
    "Título variação 3 (foco em resultado)"
  ],
  "descricao": "Texto completo da descrição com capítulos\\n\\n0:00 - Introdução\\n0:XX - Capítulo 1\\n...",
  "tags": ["tag1", "tag2", "tag3"],
  "playlist_sugerida": "Nome da playlist sugerida",
  "playlist_nova": false
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


async def gerar_metadata_publicacao(roteiro: Roteiro) -> dict:
    """
    Gera metadata de publicação para um roteiro finalizado.

    Args:
        roteiro: Roteiro completo com vídeo finalizado

    Returns:
        Dict com titulos, descricao, tags, playlist_sugerida

    Raises:
        RuntimeError: Se falhar na geração
    """
    # Preparar resumo das cenas para capítulos
    cenas_resumo = []
    timestamp_acumulado = 0.0

    for cena in roteiro.cenas:
        minutos = int(timestamp_acumulado // 60)
        segundos = int(timestamp_acumulado % 60)
        timestamp_str = f"{minutos:02d}:{segundos:02d}"

        cenas_resumo.append(
            f"{timestamp_str} - {cena.texto_locucao[:80]}..."
            if len(cena.texto_locucao) > 80
            else f"{timestamp_str} - {cena.texto_locucao}"
        )

        timestamp_acumulado += cena.duracao_estimada_segundos

    cenas_texto = "\n".join(cenas_resumo)

    prompt = PROMPT_METADATA.format(
        titulo_original=roteiro.metadata.titulo_sugerido,
        nicho=roteiro.metadata.nicho,
        formato=roteiro.metadata.formato,
        duracao=roteiro.metadata.duracao_estimada_segundos,
        cenas_resumo=cenas_texto,
    )

    try:
        resposta_bruta = await complete_cloud(
            prompt,
            model=settings.cloud_model_roteiro,
            operacao="metadata_seo",
            nicho=roteiro.metadata.nicho,
            video_id=roteiro.metadata.video_id,
        )
        texto_limpo = _limpar_resposta_json(resposta_bruta)
        metadata = json.loads(texto_limpo)

        # Validar campos obrigatórios
        campos_obrigatorios = ["titulos", "descricao", "tags", "playlist_sugerida"]
        for campo in campos_obrigatorios:
            if campo not in metadata:
                raise ValueError(f"Campo obrigatório ausente: {campo}")

        logger.info(
            "metadata_gerada.sucesso",
            extra={
                "video_id": roteiro.metadata.video_id,
                "num_titulos": len(metadata.get("titulos", [])),
                "num_tags": len(metadata.get("tags", [])),
            },
        )

        return metadata

    except json.JSONDecodeError as e:
        logger.error(
            "metadata_gerada.json_invalido",
            extra={"erro": str(e), "resposta": texto_limpo[:500]},
        )
        raise RuntimeError(f"JSON inválido na geração de metadata: {e}") from e
    except Exception as e:
        logger.error(
            "metadata_gerada.erro",
            extra={"erro": str(e)},
        )
        raise RuntimeError(f"Erro na geração de metadata: {e}") from e


def formatar_metadata_cli(metadata: dict) -> str:
    """
    Formata metadata para exibição via CLI.

    Args:
        metadata: Dict com titulos, descricao, tags, playlist_sugerida

    Returns:
        String formatada para terminal
    """
    linhas = []

    linhas.append("=" * 80)
    linhas.append("METADATA DE PUBLICAÇÃO")
    linhas.append("=" * 80)

    # Títulos
    linhas.append("\n📌 TÍTULOS SUGERIDOS:")
    for i, titulo in enumerate(metadata.get("titulos", []), 1):
        linhas.append(f"  {i}. {titulo}")

    # Descrição
    linhas.append("\n📝 DESCRIÇÃO:")
    linhas.append(metadata.get("descricao", ""))

    # Tags
    linhas.append("\n🏷️  TAGS:")
    tags = metadata.get("tags", [])
    linhas.append(f"  {', '.join(tags)}")

    # Playlist
    linhas.append("\n📂 PLAYLIST SUGERIDA:")
    linhas.append(f"  {metadata.get('playlist_sugerida', 'N/A')}")

    linhas.append("\n" + "=" * 80)
    linhas.append("Copie e cole manualmente no YouTube Studio")
    linhas.append("=" * 80)

    return "\n".join(linhas)
