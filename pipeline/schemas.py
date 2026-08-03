"""
Schemas Pydantic — a "fonte da verdade" estrutural do pipeline.

Toda etapa (ideação, roteirização, áudio, assets, render) lê e escreve
objetos validados por estes modelos. Substitui o parser manual em
JavaScript/regex usado no fluxo n8n original por validação de schema real,
com erros claros e tipados quando o LLM retorna algo fora do formato.
"""
from enum import Enum
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fase 1 — Ideação
# ---------------------------------------------------------------------------

class Ideia(BaseModel):
    topico: str
    titulo_sugerido: str
    descricao_breve: str


class RespostaIdeacao(BaseModel):
    ideias: list[Ideia] = Field(min_length=5, max_length=5)


# ---------------------------------------------------------------------------
# Fase 2 — Roteirização
# ---------------------------------------------------------------------------

class TipoAsset(str, Enum):
    imagem = "imagem"
    video = "video"


class AnimacaoImagem(str, Enum):
    ken_burns_zoom_in = "ken_burns_zoom_in"
    ken_burns_zoom_out = "ken_burns_zoom_out"
    pan_lateral = "pan_lateral"


class Midia(BaseModel):
    tipo_asset_preferencial: TipoAsset
    keywords_busca: list[str] = Field(min_length=1)
    fallback_query: str
    duracao_minima: float


class EfeitosVisuais(BaseModel):
    animacao_imagem: AnimacaoImagem
    transicao_saida: str = "fade"
    duracao_transicao_segundos: float = 0.5


class Overlays(BaseModel):
    exibir_legenda: bool = True
    texto_destaque_tela: str | None = None


class Palavra(BaseModel):
    """Timestamp por palavra, gerado pelo Faster-Whisper na Fase 3."""
    text: str
    start: float
    end: float


class Cena(BaseModel):
    cena_id: int
    ordem: int
    texto_locucao: str
    duracao_estimada_segundos: float
    midia: Midia
    efeitos_visuais: EfeitosVisuais
    overlays: Overlays

    # Preenchidos automaticamente pela Fase 3 (áudio)
    audio_path: str | None = None
    palavras_transcritas: list[Palavra] | None = None
    wer_final: float | None = None
    revisao_manual_necessaria: bool = False

    # Preenchido automaticamente pela Fase 4 (assets)
    asset_resolvido_path: str | None = None
    asset_origem: str | None = None  # "banco_local" | "fallback_pexels" | etc.


class MetadataRoteiro(BaseModel):
    video_id: str
    nicho: str
    titulo_sugerido: str
    duracao_estimada_segundos: float
    trilha_fundo: str
    volume_trilha_fundo: float = 0.15

    # Preenchidos automaticamente pela Fase 3
    audio_final_path: str | None = None
    palavras_transcritas: list[Palavra] | None = None


class Roteiro(BaseModel):
    metadata: MetadataRoteiro
    cenas: list[Cena]
