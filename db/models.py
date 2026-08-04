"""
Modelos SQLAlchemy.

`VideoIdeia` é o equivalente direto da tabela `dados.videos_ideias` já
existente no Postgres usado pelo fluxo n8n original — o schema abaixo foi
mantido compatível para permitir migração direta dos dados existentes.

`Roteiro` e `ExecucaoPipeline` são novas tabelas, propostas para dar
rastreabilidade ao pipeline Python (fases 2 em diante) — não existiam no
fluxo n8n original.
"""
import datetime as dt

from sqlalchemy import String, Text, DateTime, Float, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.session import AsyncSessionLocal


class Base(DeclarativeBase):
    pass


class VideoIdeia(Base):
    __tablename__ = "videos_ideias"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    topico: Mapped[str] = mapped_column(String, nullable=False)
    titulo_sugerido: Mapped[str] = mapped_column(String, nullable=False)
    descricao_breve: Mapped[str] = mapped_column(Text, nullable=True)
    nicho: Mapped[str] = mapped_column(String, nullable=False, default="cultura_pop")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pendente")
    data_criacao: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class RoteiroDB(Base):
    """Persistência de roteiros gerados na Fase 2."""
    __tablename__ = "roteiros"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    nicho: Mapped[str] = mapped_column(String, nullable=False)
    titulo_sugerido: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ExecucaoPipeline(Base):
    """Rastreabilidade de cada execução completa do pipeline (Fase 6)."""
    __tablename__ = "execucoes_pipeline"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String, nullable=False)
    nicho: Mapped[str] = mapped_column(String, nullable=False)
    etapa_atual: Mapped[str] = mapped_column(String, nullable=False, default="ideacao")
    sucesso: Mapped[bool] = mapped_column(Boolean, nullable=True)
    caminho_video_final: Mapped[str] = mapped_column(String, nullable=True)
    wer_medio: Mapped[float] = mapped_column(Float, nullable=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Helpers de acesso — usados pelos services/ (mantém SQL fora dos agentes)
# ---------------------------------------------------------------------------

async def salvar_ideias(ideias: list) -> None:
    """
    Persiste a lista de `Ideia` (pipeline.schemas.Ideia) retornada pelo
    agente de ideação. Equivalente ao nó "Insert rows in a table" do n8n.
    """
    async with AsyncSessionLocal() as session:
        for ideia in ideias:
            registro = VideoIdeia(
                topico=ideia.topico,
                titulo_sugerido=ideia.titulo_sugerido,
                descricao_breve=ideia.descricao_breve,
                nicho=ideia.nicho or "cultura_pop",
            )
            session.add(registro)
        await session.commit()


async def buscar_titulos_recentes_db(nicho: str, limite: int = 30) -> list[str]:
    """Implementação real para services/ideation/rag_client.py (Fase 1)."""
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = (
            select(VideoIdeia.titulo_sugerido)
            .where(VideoIdeia.nicho == nicho)
            .order_by(VideoIdeia.data_criacao.desc())
            .limit(limite)
        )
        resultado = await session.execute(stmt)
        return [row[0] for row in resultado.all()]


async def salvar_roteiro(roteiro) -> str:
    """
    Persiste um `Roteiro` (pipeline.schemas.Roteiro) gerado na Fase 2.
    Retorna o video_id do roteiro salvo.
    """
    import json
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Verificar se já existe roteiro com este video_id
        stmt = select(RoteiroDB).where(RoteiroDB.video_id == roteiro.metadata.video_id)
        resultado = await session.execute(stmt)
        existente = resultado.scalar_one_or_none()

        if existente:
            # Atualizar existente
            existente.payload_json = roteiro.model_dump_json()
            existente.titulo_sugerido = roteiro.metadata.titulo_sugerido
            existente.nicho = roteiro.metadata.nicho
        else:
            # Criar novo
            registro = RoteiroDB(
                video_id=roteiro.metadata.video_id,
                nicho=roteiro.metadata.nicho,
                titulo_sugerido=roteiro.metadata.titulo_sugerido,
                payload_json=roteiro.model_dump_json(),
            )
            session.add(registro)

        await session.commit()
        return roteiro.metadata.video_id


async def buscar_roteiro(video_id: str):
    """Recupera um roteiro salvo pelo video_id. Retorna o objeto Roteiro ou None."""
    import json
    from pipeline.schemas import Roteiro
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(RoteiroDB).where(RoteiroDB.video_id == video_id)
        resultado = await session.execute(stmt)
        registro = resultado.scalar_one_or_none()

        if not registro:
            return None

        dados = json.loads(registro.payload_json)
        return Roteiro.model_validate(dados)


async def salvar_execucao(roteiro: dict, caminho_final: str) -> None:
    """TODO (Fase 6): persistir o resultado final de uma execução completa."""
    raise NotImplementedError("Fase 6: implementar rastreabilidade de execuções completas.")