"""
API HTTP para consulta de status do pipeline.

Endpoints:
- GET /execucoes?nicho=&status= — lista execuções com filtro opcional
- GET /execucoes/{video_id} — detalhe de uma execução específica

Não inclui webhook de disparo — o APScheduler já cobre agendamento.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from db.models import ExecucaoPipeline
from db.session import AsyncSessionLocal
from sqlalchemy import select

router = APIRouter()


class ExecucaoResumo(BaseModel):
    """Resumo de uma execução para listagem."""
    video_id: str
    nicho: str
    etapa_atual: str
    sucesso: Optional[bool] = None
    motivo_falha: Optional[str] = None
    criado_em: str


class MetadataPublicacaoResposta(BaseModel):
    """Metadata de publicação para YouTube."""
    titulos: list[str]
    descricao: str
    tags: list[str]
    playlist_sugerida: str
    playlist_nova: bool


class IdeiaManualCreate(BaseModel):
    """Payload para criar uma ideia manual."""
    nicho: str
    titulo_sugerido: str
    descricao_breve: Optional[str] = None
    tendencia_relacionada: Optional[str] = None
    prioridade: str = "normal"  # "alta" ou "normal"


class IdeiaManualResposta(BaseModel):
    """Resposta de uma ideia manual."""
    id: int
    nicho: str
    titulo_sugerido: str
    descricao_breve: Optional[str] = None
    tendencia_relacionada: Optional[str] = None
    prioridade: str
    status: str
    video_id: Optional[str] = None
    criado_em: str


class ExecucaoDetalhe(BaseModel):
    """Detalhes completos de uma execução."""
    video_id: str
    nicho: str
    etapa_atual: str
    sucesso: Optional[bool] = None
    caminho_video_final: Optional[str] = None
    wer_medio: Optional[float] = None
    motivo_falha: Optional[str] = None
    criado_em: str


@router.get("/execucoes", response_model=list[ExecucaoResumo])
async def listar_execucoes(
    nicho: Optional[str] = Query(None, description="Filtrar por nicho"),
    status: Optional[str] = Query(None, description="Filtrar por status (sucesso/falha)"),
    limite: int = Query(50, ge=1, le=500, description="Número máximo de registros"),
):
    """
    Lista execuções do pipeline com filtros opcionais.

    - **nicho**: Filtrar por nicho específico (cultura_pop, tecnologia, futebol)
    - **status**: Filtrar por status (sucesso, falha)
    - **limite**: Número máximo de registros a retornar
    """
    async with AsyncSessionLocal() as session:
        stmt = select(ExecucaoPipeline).order_by(ExecucaoPipeline.criado_em.desc()).limit(limite)

        if nicho:
            stmt = stmt.where(ExecucaoPipeline.nicho == nicho)

        if status:
            if status.lower() == "sucesso":
                stmt = stmt.where(ExecucaoPipeline.sucesso == True)
            elif status.lower() == "falha":
                stmt = stmt.where(ExecucaoPipeline.sucesso == False)

        resultado = await session.execute(stmt)
        execucoes = resultado.scalars().all()

        return [
            ExecucaoResumo(
                video_id=exec_.video_id,
                nicho=exec_.nicho,
                etapa_atual=exec_.etapa_atual,
                sucesso=exec_.sucesso,
                motivo_falha=exec_.motivo_falha,
                criado_em=exec_.criado_em.isoformat() if exec_.criado_em else "",
            )
            for exec_ in execucoes
        ]


@router.get("/execucoes/{video_id}", response_model=ExecucaoDetalhe)
async def obter_execucao(video_id: str):
    """
    Obtém detalhes de uma execução específica por video_id.

    Retorna:
    - Etapa atual/última etapa concluída
    - Status de sucesso/falha
    - Motivo da falha (se houver)
    - Caminho do vídeo final (se sucesso)
    - WER médio do áudio (se sucesso)
    """
    async with AsyncSessionLocal() as session:
        stmt = select(ExecucaoPipeline).where(ExecucaoPipeline.video_id == video_id)
        resultado = await session.execute(stmt)
        execucao = resultado.scalar_one_or_none()

        if not execucao:
            raise HTTPException(status_code=404, detail=f"Execução com video_id '{video_id}' não encontrada")

        return ExecucaoDetalhe(
            video_id=execucao.video_id,
            nicho=execucao.nicho,
            etapa_atual=execucao.etapa_atual,
            sucesso=execucao.sucesso,
            caminho_video_final=execucao.caminho_video_final,
            wer_medio=execucao.wer_medio,
            motivo_falha=execucao.motivo_falha,
            criado_em=execucao.criado_em.isoformat() if execucao.criado_em else "",
        )


@router.get("/execucoes/{video_id}/metadata", response_model=MetadataPublicacaoResposta)
async def obter_metadata_publicacao(video_id: str):
    """
    Obtém metadata de publicação para o vídeo (Subfase 8.6).

    Retorna:
    - Títulos otimizados (2-3 variações)
    - Descrição com capítulos timestampados
    - Tags relevantes
    - Sugestão de playlist

    Raises:
    - 404: Se vídeo não encontrado ou metadata não gerada
    """
    from db.models import carregar_roteiro
    from pipeline.schemas import Roteiro

    roteiro = await carregar_roteiro(video_id)

    if not roteiro:
        raise HTTPException(status_code=404, detail=f"Vídeo '{video_id}' não encontrado")

    if not roteiro.metadata.metadata_publicacao:
        raise HTTPException(
            status_code=404,
            detail=f"Metadata de publicação não gerada para vídeo '{video_id}'. "
                   f"Execute o pipeline completo primeiro."
        )

    metadata = roteiro.metadata.metadata_publicacao

    return MetadataPublicacaoResposta(
        titulos=metadata.titulos,
        descricao=metadata.descricao,
        tags=metadata.tags,
        playlist_sugerida=metadata.playlist_sugerida,
        playlist_nova=metadata.playlist_nova,
    )


# ---------------------------------------------------------------------------
# Ideias Manuais (Subfase 8.8 — Painel de controle editorial)
# ---------------------------------------------------------------------------

@router.post("/ideias-manuais", response_model=IdeiaManualResposta, status_code=201)
async def criar_ideia_manual(ideia: IdeiaManualCreate):
    """
    Cria uma nova ideia manual.

    Ideias com prioridade "alta" substituem uma das 5 vagas do próximo lote.
    Ideias com prioridade "normal" entram como contexto adicional no prompt.
    """
    from db.models import salvar_ideia_manual

    ideia_id = await salvar_ideia_manual(
        nicho=ideia.nicho,
        titulo_sugerido=ideia.titulo_sugerido,
        descricao_breve=ideia.descricao_breve,
        tendencia_relacionada=ideia.tendencia_relacionada,
        prioridade=ideia.prioridade,
    )

    # Buscar ideia criada
    from db.models import buscar_ideia_manual_por_id
    ideia_criada = await buscar_ideia_manual_por_id(ideia_id)

    return IdeiaManualResposta(**ideia_criada)


@router.get("/ideias-manuais", response_model=list[IdeiaManualResposta])
async def listar_ideias_manuais(
    nicho: Optional[str] = None,
    status: Optional[str] = None,
    limite: int = 50,
):
    """
    Lista ideias manuais com filtros opcionais.

    Parâmetros:
    - nicho: Filtrar por nicho
    - status: Filtrar por status (pendente, usada, descartada)
    - limite: Número máximo de registros (default: 50)
    """
    from db.models import listar_ideias_manuais as _listar_ideias_manuais

    ideias = await _listar_ideias_manuais(nicho=nicho, status=status, limite=limite)
    return [IdeiaManualResposta(**ideia) for ideia in ideias]


@router.delete("/ideias-manuais/{ideia_id}")
async def descartar_ideia_manual(ideia_id: int):
    """
    Descarta uma ideia manual (marca status como 'descartada').

    Raises:
    - 404: Se ideia não encontrada
    """
    from db.models import marcar_ideia_manual_descartada

    sucesso = await marcar_ideia_manual_descartada(ideia_id)

    if not sucesso:
        raise HTTPException(status_code=404, detail=f"Ideia {ideia_id} não encontrada")

    return {"message": "Ideia descartada com sucesso", "id": ideia_id}


# Health check está definido em api/main.py
