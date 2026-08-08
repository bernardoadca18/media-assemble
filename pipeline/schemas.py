"""
Schemas Pydantic — a "fonte da verdade" estrutural do pipeline.

Toda etapa (ideação, roteirização, áudio, render) lê e escreve
objetos validados por estes modelos. Substitui o parser manual em
JavaScript/regex usado no fluxo n8n original por validação de schema real,
com erros claros e tipados quando o LLM retorna algo fora do formato.
"""
from enum import Enum
from typing import Literal, Union
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Fase 1 — Ideação
# ---------------------------------------------------------------------------

class Ideia(BaseModel):
    topico: str
    titulo_sugerido: str
    descricao_breve: str
    # Preenchido programaticamente por services/ideation/agent.py após a
    # resposta do LLM (o LLM não precisa e não deve gerar este campo) —
    # mantido opcional aqui para não quebrar a validação da resposta bruta.
    nicho: str | None = None
    # Sinaliza que a ideia não pôde ser substituída após detectar duplicidade
    # semântica e requer revisão manual antes de prosseguir
    requer_revisao_manual: bool = False
    motivo_revisao: str | None = None
    # Subfase 8.8 — Ideia manual injetada pelo usuário
    ideia_manual_id: int | None = None  # ID da ideia manual se veio do painel de controle


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


class EstiloVisual(str, Enum):
    """Estilos visuais disponíveis para renderização de cenas."""
    ken_burns = "ken_burns"
    vox_motion = "vox_motion"
    gameplay_bg = "gameplay_bg"


# ---------------------------------------------------------------------------
# Elementos gráficos para estilo vox_motion
# ---------------------------------------------------------------------------

class ComparacaoNumerica(BaseModel):
    """Comparação numérica estilo Vox (ex: '150 milhões de views')."""
    valor_principal: str
    rotulo_principal: str
    valor_comparacao: str | None = None
    rotulo_comparacao: str | None = None
    unidade: str = ""


class LinhaDoTempo(BaseModel):
    """Linha do tempo estilo Vox para eventos sequenciais."""
    eventos: list[str] = Field(min_length=2, max_length=10)
    ano_inicio: str | None = None
    ano_fim: str | None = None
    titulo: str | None = None


class Citacao(BaseModel):
    """Citação estilo Vox com destaque visual."""
    texto: str
    autor: str
    contexto: str | None = None


class GraficoComparativo(BaseModel):
    """Gráfico de barras comparativo estilo Vox."""
    itens: list[str] = Field(min_length=2, max_length=6)
    valores: list[str] = Field(min_length=2, max_length=6)
    titulo: str
    unidade: str = ""


# Union type para todos os elementos gráficos possíveis
ElementoGrafico = Union[ComparacaoNumerica, LinhaDoTempo, Citacao, GraficoComparativo]


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

    # Subfase 8.4 — Estilo visual Vox
    # Fase 9.2 — Estilo visual gameplay_bg
    estilo_visual: Literal["ken_burns", "vox_motion", "gameplay_bg"] = "ken_burns"
    elemento_grafico: ElementoGrafico | None = None

    # Fase 9.4 — Recorte vertical para gameplay_bg em Shorts
    crop_offset_y: int = 0  # Offset Y em pixels para ajustar enquadramento

    # Preenchidos automaticamente pela Fase 3 (áudio)
    audio_path: str | None = None
    palavras_transcritas: list[Palavra] | None = None
    wer_final: float | None = None
    revisao_manual_necessaria: bool = False

    # Preenchido automaticamente pela Fase 4 (assets)
    asset_resolvido_path: str | None = None
    asset_origem: str | None = None  # "banco_local" | "fallback_pexels" | etc.


class MetadataPublicacao(BaseModel):
    """Metadata de publicação para YouTube (Subfase 8.6)."""
    titulos: list[str] = Field(min_length=2, max_length=3, description="2-3 variações de título")
    descricao: str = Field(description="Descrição completa com capítulos")
    tags: list[str] = Field(max_length=15, description="Tags relevantes (máx 15)")
    playlist_sugerida: str = Field(description="Nome da playlist sugerida")
    playlist_nova: bool = Field(default=False, description="Se deve criar nova playlist")


class MetadataRoteiro(BaseModel):
    video_id: str
    nicho: str
    titulo_sugerido: str
    duracao_estimada_segundos: float
    trilha_fundo: str
    volume_trilha_fundo: float = 0.15

    # Subfase 8.5 — Suporte a Shorts
    formato: Literal["longo", "short"] = "longo"
    video_origem_id: str | None = None  # Se for short derivado de vídeo longo

    # Preenchidos automaticamente pela Fase 3
    audio_final_path: str | None = None
    palavras_transcritas: list[Palavra] | None = None

    # Preenchido automaticamente pela Fase 5
    video_final_path: str | None = None

    # Subfase 8.6 — Metadata de publicação
    metadata_publicacao: MetadataPublicacao | None = None

    def model_post_init(self, __context):
        """Valida duração para formato short."""
        if self.formato == "short":
            if not (25.0 <= self.duracao_estimada_segundos <= 58.0):
                raise ValueError(
                    f"Shorts devem ter duração entre 25s e 58s. "
                    f"Recebido: {self.duracao_estimada_segundos}s"
                )


class Roteiro(BaseModel):
    metadata: MetadataRoteiro
    cenas: list[Cena]
