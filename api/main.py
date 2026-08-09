"""
API HTTP principal do Faceless Pipeline.

Este módulo configura o FastAPI com:
- CORS restrito ao frontend local
- Bind em 127.0.0.1 (nunca 0.0.0.0)
- Todos os endpoints de gestão do pipeline

IMPORTANTE: Esta API deve sempre escutar em 127.0.0.1 para uso local.
Antes de expor além de localhost, adicionar autenticação por API key.

Uso:
    uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
"""
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Importar funções do pipeline
from db.models import (
    listar_roteiros_pendentes_revisao,
    atualizar_status_revisao,
    buscar_gameplay_segmentos,
    salvar_execucao,
    buscar_execucao_falha,
)
from pipeline.orchestrator import retomar_execucao_falha
from pipeline.gpu_lock import gpu_status
from pipeline.nichos import NICHOS_CONFIG, listar_nichos_disponiveis


# Lifespan para inicialização
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 Faceless Pipeline API iniciada")
    print("⚠️  Bind: 127.0.0.1 (apenas localhost)")
    print("⚠️  Autenticação: desabilitada (uso local)")
    yield
    # Shutdown
    print("👋 Faceless Pipeline API encerrada")


# Criar aplicação FastAPI
app = FastAPI(
    title="Faceless Pipeline API",
    description="API de gestão do pipeline de geração de vídeos faceless",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - restrito ao frontend local
# TODO: Antes de expor além de localhost, adicionar autenticação por API key
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:5173",  # Vite dev server (alternativo)
        "http://localhost:3000",  # Alternativa comum
        "http://127.0.0.1:3000",  # Alternativa comum
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check básico para monitoramento."""
    from datetime import datetime
    return {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "bind": "127.0.0.1",
        "auth": "disabled (local use only)",
    }


# ---------------------------------------------------------------------------
# Execuções - Retomar
# ---------------------------------------------------------------------------

class RetomarResposta(BaseModel):
    """Resposta da ação de retomar execução."""
    sucesso: bool
    video_id: str
    mensagem: str
    etapa_retomada: Optional[str] = None


@app.post("/execucoes/{video_id}/retomar", response_model=RetomarResposta)
async def retomar_execucao(video_id: str):
    """
    Retoma uma execução falha a partir da última etapa concluída.

    Reaproveita a lógica de retomar_execucao_falha do orchestrator.

    Args:
        video_id: ID do vídeo a ser retomado

    Returns:
        Resultado da retomada (sucesso/falha)
    """
    # Verificar se execução existe
    execucao = await buscar_execucao_falha(video_id)
    if not execucao:
        raise HTTPException(
            status_code=404,
            detail=f"Execução {video_id} não encontrada ou não está em estado falho"
        )

    try:
        resultado = await retomar_execucao_falha(video_id)

        return RetomarResposta(
            sucesso=resultado.get("sucesso", False),
            video_id=video_id,
            mensagem="Execução retomada com sucesso" if resultado.get("sucesso") else resultado.get("erro", "Falha ao retomar"),
            etapa_retomada=resultado.get("etapa"),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro ao retomar execução: {str(e)}"
        )


# ---------------------------------------------------------------------------
# Revisão Manual
# ---------------------------------------------------------------------------

class RoteiroPendenteResposta(BaseModel):
    """Resposta de roteiro pendente de revisão."""
    video_id: str
    nicho: str
    titulo_sugerido: str
    criado_em: str


class RevisaoResposta(BaseModel):
    """Resposta da ação de revisão."""
    sucesso: bool
    video_id: str
    novo_status: str
    mensagem: str


@app.get("/revisao/pendentes", response_model=list[RoteiroPendenteResposta])
async def listar_pendentes_revisao(limite: int = Query(default=50, ge=1, le=200)):
    """
    Lista roteiros pendentes de revisão manual.

    Args:
        limite: Número máximo de registros (1-200)

    Returns:
        Lista de roteiros pendentes
    """
    roteiros = await listar_roteiros_pendentes_revisao(limite=limite)
    return [
        RoteiroPendenteResposta(**r) for r in roteiros
    ]


@app.post("/revisao/{video_id}/aprovar", response_model=RevisaoResposta)
async def aprovar_roteiro(video_id: str):
    """
    Aprova um roteiro pendente de revisão.

    Args:
        video_id: ID do vídeo/roteiro

    Returns:
        Confirmação da aprovação
    """
    sucesso = await atualizar_status_revisao(video_id, "aprovado")

    if not sucesso:
        raise HTTPException(
            status_code=404,
            detail=f"Roteiro {video_id} não encontrado"
        )

    return RevisaoResposta(
        sucesso=True,
        video_id=video_id,
        novo_status="aprovado",
        mensagem="Roteiro aprovado com sucesso"
    )


@app.post("/revisao/{video_id}/rejeitar", response_model=RevisaoResposta)
async def rejeitar_roteiro(video_id: str):
    """
    Rejeita um roteiro pendente de revisão.

    Args:
        video_id: ID do vídeo/roteiro

    Returns:
        Confirmação da rejeição
    """
    sucesso = await atualizar_status_revisao(video_id, "rejeitado")

    if not sucesso:
        raise HTTPException(
            status_code=404,
            detail=f"Roteiro {video_id} não encontrado"
        )

    return RevisaoResposta(
        sucesso=True,
        video_id=video_id,
        novo_status="rejeitado",
        mensagem="Roteiro rejeitado"
    )


# ---------------------------------------------------------------------------
# Gameplay
# ---------------------------------------------------------------------------

class SegmentoGameplayResposta(BaseModel):
    """Resposta de segmento de gameplay."""
    id: int
    jogo_origem: str
    caminho_arquivo: str
    duracao_segundos: float
    score_movimento: float
    faixa_intensidade: str
    usado_em: list[str]
    criado_em: str


class EstatisticasGameplayResposta(BaseModel):
    """Estatísticas de gameplay por jogo."""
    jogo: str
    total_segmentos: int
    duracao_total_segundos: float
    duracao_total_formatada: str
    aprovados: int
    rejeitados: int
    taxa_aprovacao: float


@app.get("/gameplay/segmentos", response_model=list[SegmentoGameplayResposta])
async def listar_segmentos_gameplay(
    jogo: Optional[str] = Query(default=None),
    intensidade: Optional[str] = Query(default=None),
    limite: int = Query(default=50, ge=1, le=500)
):
    """
    Lista segmentos de gameplay indexados.

    Args:
        jogo: Filtrar por jogo (opcional)
        intensidade: Filtrar por intensidade (calmo, moderado, intenso)
        limite: Número máximo de registros

    Returns:
        Lista de segmentos
    """
    segmentos = await buscar_gameplay_segmentos(
        jogo=jogo,
        faixa_intensidade=intensidade,
        limite=limite
    )

    return [
        SegmentoGameplayResposta(
            id=seg["id"],
            jogo_origem=seg["jogo_origem"],
            caminho_arquivo=seg["caminho_arquivo"],
            duracao_segundos=seg["duracao_segundos"],
            score_movimento=seg["score_movimento"],
            faixa_intensidade=seg["faixa_intensidade"],
            usado_em=seg.get("usado_em", []),
            criado_em=seg["criado_em"],
        )
        for seg in segmentos
    ]


@app.get("/gameplay/estatisticas", response_model=list[EstatisticasGameplayResposta])
async def estatisticas_gameplay():
    """
    Estatísticas agregadas por jogo.

    Returns:
        Lista de estatísticas por jogo
    """
    from sqlalchemy import func, select
    from db.models import GameplaySegmento
    from db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        # Query agregada por jogo
        stmt = (
            select(
                GameplaySegmento.jogo_origem,
                func.count(GameplaySegmento.id).label("total"),
                func.sum(GameplaySegmento.duracao_segundos).label("duracao_total"),
                func.avg(GameplaySegmento.score_movimento).label("score_medio"),
            )
            .group_by(GameplaySegmento.jogo_origem)
            .order_by(GameplaySegmento.jogo_origem)
        )

        resultado = await session.execute(stmt)
        rows = resultado.all()

        estatisticas = []
        for row in rows:
            duracao_total = row.duracao_total or 0
            horas = int(duracao_total // 3600)
            minutos = int((duracao_total % 3600) // 60)
            segundos = int(duracao_total % 60)

            duracao_formatada = f"{horas:02d}:{minutos:02d}:{segundos:02d}" if horas > 0 else f"{minutos:02d}:{segundos:02d}"

            estatisticas.append(
                EstatisticasGameplayResposta(
                    jogo=row.jogo_origem,
                    total_segmentos=row.total,
                    duracao_total_segundos=duracao_total,
                    duracao_total_formatada=duracao_formatada,
                    aprovados=row.total,  # Simplificação: todos os indexados são aprovados
                    rejeitados=0,  # Não rastreamos rejeitados separadamente
                    taxa_aprovacao=100.0,  # Simplificação
                )
            )

        return estatisticas


# ---------------------------------------------------------------------------
# Nichos
# ---------------------------------------------------------------------------

class NichoResposta(BaseModel):
    """Configuração de um nicho."""
    nome: str
    categoria_google_trends: int
    subreddits_sugeridos: list[str]
    gameplay_intensidade_preferida: str
    prompt_roteiro_short_configurado: bool
    timbre_pitch_shift: Optional[float] = None
    timbre_velocidade: Optional[float] = None


@app.get("/nichos", response_model=list[NichoResposta])
async def listar_nichos():
    """
    Lista configurações de todos os nichos.

    Returns:
        Lista de configurações de nicho
    """
    from db.models import listar_nichos as db_listar_nichos

    # Buscar do banco
    nichos_db = await db_listar_nichos(apenas_ativos=False)

    if nichos_db:
        return [
            NichoResposta(
                nome=nicho["nome"],
                categoria_google_trends=nicho["categoria_google_trends"],
                subreddits_sugeridos=nicho["subreddits_sugeridos"],
                gameplay_intensidade_preferida=nicho["gameplay_intensidade_preferida"],
                prompt_roteiro_short_configurado=bool(nicho["prompt_roteiro_short"]),
                timbre_pitch_shift=nicho["pitch_shift_semitons"],
                timbre_velocidade=nicho["velocidade_fala"],
            )
            for nicho in nichos_db
        ]

    # Fallback para config hardcoded se banco vazio
    nichos = []
    for nome, config in NICHOS_CONFIG.items():
        nichos.append(
            NichoResposta(
                nome=config.nome,
                categoria_google_trends=config.categoria_google_trends,
                subreddits_sugeridos=config.subreddits_sugeridos,
                gameplay_intensidade_preferida=config.gameplay_intensidade_preferida,
                prompt_roteiro_short_configurado=bool(config.prompt_roteiro_short),
                timbre_pitch_shift=config.pitch_shift_semitons,
                timbre_velocidade=config.velocidade_fala,
            )
        )

    return nichos


@app.get("/nichos/{nicho}", response_model=NichoResposta)
async def obter_nicho(nicho: str):
    """
    Obtém configuração de um nicho específico.

    Args:
        nicho: Nome do nicho

    Returns:
        Configuração do nicho
    """
    from db.models import buscar_nicho_por_nome

    # Buscar do banco
    nicho_db = await buscar_nicho_por_nome(nicho)

    if nicho_db:
        return NichoResposta(
            nome=nicho_db["nome"],
            categoria_google_trends=nicho_db["categoria_google_trends"],
            subreddits_sugeridos=nicho_db["subreddits_sugeridos"],
            gameplay_intensidade_preferida=nicho_db["gameplay_intensidade_preferida"],
            prompt_roteiro_short_configurado=bool(nicho_db["prompt_roteiro_short"]),
            timbre_pitch_shift=nicho_db["pitch_shift_semitons"],
            timbre_velocidade=nicho_db["velocidade_fala"],
        )

    # Fallback para config hardcoded
    from pipeline.nichos import obter_config_nicho

    try:
        config = obter_config_nicho(nicho)
        return NichoResposta(
            nome=config.nome,
            categoria_google_trends=config.categoria_google_trends,
            subreddits_sugeridos=config.subreddits_sugeridos,
            gameplay_intensidade_preferida=config.gameplay_intensidade_preferida,
            prompt_roteiro_short_configurado=bool(config.prompt_roteiro_short),
            timbre_pitch_shift=config.pitch_shift_semitons,
            timbre_velocidade=config.velocidade_fala,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


class NichoCreate(BaseModel):
    """Schema para criar novo nicho."""
    nome: str
    prompt_ideacao: str
    prompt_roteiro_adicional: str
    prompt_roteiro_short: str
    categoria_google_trends: int
    subreddits_sugeridos: list[str]
    gameplay_intensidade_preferida: str = "moderado"
    timbre_pitch_shift: Optional[float] = None
    timbre_velocidade: Optional[float] = None


class NichoUpdate(BaseModel):
    """Schema para atualizar nicho."""
    prompt_ideacao: Optional[str] = None
    prompt_roteiro_adicional: Optional[str] = None
    prompt_roteiro_short: Optional[str] = None
    categoria_google_trends: Optional[int] = None
    subreddits_sugeridos: Optional[list[str]] = None
    gameplay_intensidade_preferida: Optional[str] = None
    timbre_pitch_shift: Optional[float] = None
    timbre_velocidade: Optional[float] = None
    ativo: Optional[bool] = None


@app.post("/nichos", response_model=NichoResposta, status_code=201)
async def criar_nicho(data: NichoCreate):
    """
    Cria um novo nicho.

    Args:
        data: Dados do novo nicho

    Returns:
        Nicho criado
    """
    from db.models import salvar_nicho, buscar_nicho_por_nome

    # Verificar se já existe
    existente = await buscar_nicho_por_nome(data.nome)
    if existente:
        raise HTTPException(status_code=400, detail=f"Nicho '{data.nome}' já existe")

    # Criar
    await salvar_nicho(
        nome=data.nome,
        prompt_ideacao=data.prompt_ideacao,
        prompt_roteiro_adicional=data.prompt_roteiro_adicional,
        prompt_roteiro_short=data.prompt_roteiro_short,
        categoria_google_trends=data.categoria_google_trends,
        subreddits_sugeridos=data.subreddits_sugeridos,
        gameplay_intensidade_preferida=data.gameplay_intensidade_preferida,
        pitch_shift_semitons=data.timbre_pitch_shift,
        velocidade_fala=data.timbre_velocidade,
    )

    return NichoResposta(
        nome=data.nome,
        categoria_google_trends=data.categoria_google_trends,
        subreddits_sugeridos=data.subreddits_sugeridos,
        gameplay_intensidade_preferida=data.gameplay_intensidade_preferida,
        prompt_roteiro_short_configurado=bool(data.prompt_roteiro_short),
        timbre_pitch_shift=data.timbre_pitch_shift,
        timbre_velocidade=data.timbre_velocidade,
    )


@app.put("/nichos/{nicho}", response_model=NichoResposta)
async def atualizar_nicho_endpoint(nicho: str, data: NichoUpdate):
    """
    Atualiza um nicho existente.

    Args:
        nicho: Nome do nicho
        data: Campos a atualizar

    Returns:
        Nicho atualizado
    """
    from db.models import atualizar_nicho, buscar_nicho_por_nome

    # Verificar se existe
    existente = await buscar_nicho_por_nome(nicho)
    if not existente:
        raise HTTPException(status_code=404, detail=f"Nicho '{nicho}' não encontrado")

    # Atualizar
    await atualizar_nicho(
        nome=nicho,
        prompt_ideacao=data.prompt_ideacao,
        prompt_roteiro_adicional=data.prompt_roteiro_adicional,
        prompt_roteiro_short=data.prompt_roteiro_short,
        categoria_google_trends=data.categoria_google_trends,
        subreddits_sugeridos=data.subreddits_sugeridos,
        gameplay_intensidade_preferida=data.gameplay_intensidade_preferida,
        pitch_shift_semitons=data.timbre_pitch_shift,
        velocidade_fala=data.timbre_velocidade,
        ativo=data.ativo,
    )

    # Retornar atualizado
    atualizado = await buscar_nicho_por_nome(nicho)
    return NichoResposta(
        nome=atualizado["nome"],
        categoria_google_trends=atualizado["categoria_google_trends"],
        subreddits_sugeridos=atualizado["subreddits_sugeridos"],
        gameplay_intensidade_preferida=atualizado["gameplay_intensidade_preferida"],
        prompt_roteiro_short_configurado=bool(atualizado["prompt_roteiro_short"]),
        timbre_pitch_shift=atualizado["pitch_shift_semitons"],
        timbre_velocidade=atualizado["velocidade_fala"],
    )


@app.delete("/nichos/{nicho}")
async def deletar_nicho_endpoint(nicho: str):
    """
    Remove um nicho (soft delete - marca como inativo).

    Args:
        nicho: Nome do nicho

    Returns:
        Mensagem de confirmação
    """
    from db.models import deletar_nicho, buscar_nicho_por_nome

    # Verificar se existe
    existente = await buscar_nicho_por_nome(nicho)
    if not existente:
        raise HTTPException(status_code=404, detail=f"Nicho '{nicho}' não encontrado")

    # Soft delete
    sucesso = await deletar_nicho(nicho)

    if sucesso:
        return {"mensagem": f"Nicho '{nicho}' desativado com sucesso"}
    else:
        raise HTTPException(status_code=500, detail="Erro ao desativar nicho")


# ---------------------------------------------------------------------------
# GPU Status
# ---------------------------------------------------------------------------

class GPUStatusResposta(BaseModel):
    """Status do GPU lock."""
    disponivel: bool
    mensagem: str


@app.get("/gpu-status", response_model=GPUStatusResposta)
async def status_gpu():
    """
    Verifica se a GPU está disponível ou em uso.

    Returns:
        Status do GPU lock
    """
    try:
        status = gpu_status()
        return GPUStatusResposta(
            disponivel=status["disponivel"],
            mensagem="GPU disponível" if status["disponivel"] else "GPU em uso",
        )
    except Exception as e:
        # Se gpu_status não existir, retornar disponível por padrão
        return GPUStatusResposta(
            disponivel=True,
            mensagem="GPU status não disponível",
        )


# ---------------------------------------------------------------------------
# Execuções - Reimportar do status.py
# ---------------------------------------------------------------------------

# Importar endpoints existentes de status.py
from api.status import (
    app as status_app,
    ExecucaoResumo,
    ExecucaoDetalhe,
    MetadataPublicacaoResposta,
    IdeiaManualCreate,
    IdeiaManualResposta,
)

# Re-registrar endpoints do status.py no app principal
# (isso é feito automaticamente pela importação, mas garantimos aqui)
for route in status_app.routes:
    if route.path not in [r.path for r in app.routes]:
        app.routes.append(route)
