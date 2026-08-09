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
import logging

from sqlalchemy import String, Text, DateTime, Float, Boolean, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from db.session import AsyncSessionLocal

logger = logging.getLogger("db.models")


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
    # Embedding para checagem de duplicidade semântica (Fase 8.2)
    # Dimensão 1536 = text-embedding-3-small da OpenAI
    embedding: Mapped[str | None] = mapped_column(Text, nullable=True)


class RoteiroDB(Base):
    """Persistência de roteiros gerados na Fase 2."""
    __tablename__ = "roteiros"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    video_id: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    nicho: Mapped[str] = mapped_column(String, nullable=False)
    titulo_sugerido: Mapped[str] = mapped_column(String, nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    status_revisao: Mapped[str] = mapped_column(String, nullable=False, default="pendente")  # pendente, aprovado, rejeitado
    revisado_em: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    motivo_falha: Mapped[str] = mapped_column(Text, nullable=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Nicho(Base):
    """Configuração de nichos dinâmicos (CRUD via API)."""
    __tablename__ = "nichos"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    prompt_ideacao: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_roteiro_adicional: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_roteiro_short: Mapped[str] = mapped_column(Text, nullable=False)
    categoria_google_trends: Mapped[int] = mapped_column(nullable=False)
    subreddits_sugeridos: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    gameplay_intensidade_preferida: Mapped[str] = mapped_column(String(20), nullable=False, default="moderado")
    pitch_shift_semitons: Mapped[float | None] = mapped_column(Float, nullable=True)
    velocidade_fala: Mapped[float | None] = mapped_column(Float, nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    atualizado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class IdeiaManual(Base):
    """Ideias manuais injetadas pelo usuário (Subfase 8.8)."""
    __tablename__ = "ideias_manuais"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nicho: Mapped[str] = mapped_column(String, nullable=False, index=True)
    titulo_sugerido: Mapped[str] = mapped_column(String, nullable=False)
    descricao_breve: Mapped[str | None] = mapped_column(Text, nullable=True)
    tendencia_relacionada: Mapped[str | None] = mapped_column(String, nullable=True)
    prioridade: Mapped[str] = mapped_column(String, nullable=False, default="normal")  # alta, normal
    status: Mapped[str] = mapped_column(String, nullable=False, default="pendente")  # pendente, usada, descartada
    video_id: Mapped[str | None] = mapped_column(String, nullable=True)
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ---------------------------------------------------------------------------
# Helpers de acesso — usados pelos services/ (mantém SQL fora dos agentes)
# ---------------------------------------------------------------------------

async def salvar_ideias(ideias: list, gerar_embedding: bool = True) -> None:
    """
    Persiste a lista de `Ideia` (pipeline.schemas.Ideia) retornada pelo
    agente de ideação. Equivalente ao nó "Insert rows in a table" do n8n.

    Args:
        ideias: Lista de objetos Ideia para persistir
        gerar_embedding: Se True, gera embedding para cada título (Fase 8.2)
    """
    if not gerar_embedding:
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
        return

    # Com embeddings (Fase 8.2)
    from utils.litellm_client import generate_embedding as _gerar_emb

    async with AsyncSessionLocal() as session:
        for ideia in ideias:
            # Gerar embedding para o título
            embedding_str = None
            try:
                embedding_list = await _gerar_emb(
                    text=ideia.titulo_sugerido,
                    operacao="salvar_ideia",
                    nicho=ideia.nicho,
                )
                # Converter lista para string no formato de array do Postgres
                embedding_str = "[" + ",".join(str(v) for v in embedding_list) + "]"
            except Exception as e:
                # Log erro mas não bloqueia salvamento
                import logging
                logger = logging.getLogger("db.models")
                logger.warning(
                    "salvar_ideias.erro_embedding",
                    extra={"titulo": ideia.titulo_sugerido, "erro": str(e)}
                )

            registro = VideoIdeia(
                topico=ideia.topico,
                titulo_sugerido=ideia.titulo_sugerido,
                descricao_breve=ideia.descricao_breve,
                nicho=ideia.nicho or "cultura_pop",
                embedding=embedding_str,
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


# Alias para compatibilidade
carregar_roteiro = buscar_roteiro


async def salvar_execucao(
    video_id: str | None,
    nicho: str,
    etapa_atual: str,
    sucesso: bool | None = None,
    caminho_video_final: str | None = None,
    wer_medio: float | None = None,
    motivo_falha: str | None = None,
) -> None:
    """
    Persiste o estado de uma execução do pipeline (rastreabilidade da Fase 6).

    Se já existir um registro com o mesmo video_id, atualiza (upsert).
    Se video_id for None (ex: falha na ideação antes de gerar um ID),
    cria um registro sem video_id.

    Args:
        video_id: ID único do vídeo
        nicho: Nicho do vídeo
        etapa_atual: Etapa onde a execução parou
        sucesso: True se concluiu com sucesso
        caminho_video_final: Path do vídeo renderizado (se sucesso)
        wer_medio: WER médio do áudio (se sucesso)
        motivo_falha: Mensagem de erro detalhada (se falha)
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        # Buscar registro existente (se houver video_id)
        existente = None
        if video_id:
            stmt = select(ExecucaoPipeline).where(ExecucaoPipeline.video_id == video_id)
            resultado = await session.execute(stmt)
            existente = resultado.scalar_one_or_none()

        if existente:
            # Atualizar existente
            existente.etapa_atual = etapa_atual
            existente.sucesso = sucesso
            if caminho_video_final is not None:
                existente.caminho_video_final = caminho_video_final
            if wer_medio is not None:
                existente.wer_medio = wer_medio
            if motivo_falha is not None:
                existente.motivo_falha = motivo_falha
        else:
            # Criar novo
            registro = ExecucaoPipeline(
                video_id=video_id or "",
                nicho=nicho,
                etapa_atual=etapa_atual,
                sucesso=sucesso,
                caminho_video_final=caminho_video_final,
                wer_medio=wer_medio,
                motivo_falha=motivo_falha,
            )
            session.add(registro)

        await session.commit()


async def listar_execucoes_falhas(limite: int = 50) -> list[dict]:
    """
    Lista execuções falhas (sucesso=False) que podem ser retomadas.

    Args:
        limite: Número máximo de registros a retornar

    Returns:
        Lista de dicts com {video_id, nicho, etapa_atual, motivo_falha, criado_em}
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = (
            select(ExecucaoPipeline)
            .where(ExecucaoPipeline.sucesso == False)
            .order_by(ExecucaoPipeline.criado_em.desc())
            .limit(limite)
        )
        resultado = await session.execute(stmt)
        execucoes = resultado.scalars().all()

        return [
            {
                "video_id": exec_.video_id,
                "nicho": exec_.nicho,
                "etapa_atual": exec_.etapa_atual,
                "motivo_falha": exec_.motivo_falha,
                "criado_em": exec_.criado_em.isoformat() if exec_.criado_em else None,
            }
            for exec_ in execucoes
        ]


async def buscar_execucao_falha(video_id: str) -> dict | None:
    """
    Busca uma execução falha específica pelo video_id.

    Returns:
        Dict com {video_id, nicho, etapa_atual, criado_em} ou None
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(ExecucaoPipeline).where(
            ExecucaoPipeline.video_id == video_id,
            ExecucaoPipeline.sucesso == False,
        )
        resultado = await session.execute(stmt)
        exec_ = resultado.scalar_one_or_none()

        if not exec_:
            return None

        return {
            "video_id": exec_.video_id,
            "nicho": exec_.nicho,
            "etapa_atual": exec_.etapa_atual,
            "criado_em": exec_.criado_em.isoformat() if exec_.criado_em else None,
        }


async def listar_roteiros_pendentes_revisao(limite: int = 50) -> list[dict]:
    """
    Lista roteiros com status_revisao='pendente' que aguardam aprovação.

    Args:
        limite: Número máximo de registros a retornar

    Returns:
        Lista de dicts com {video_id, nicho, titulo_sugerido, criado_em}
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = (
            select(RoteiroDB)
            .where(RoteiroDB.status_revisao == "pendente")
            .order_by(RoteiroDB.criado_em.desc())
            .limit(limite)
        )
        resultado = await session.execute(stmt)
        roteiros = resultado.scalars().all()

        return [
            {
                "video_id": r.video_id,
                "nicho": r.nicho,
                "titulo_sugerido": r.titulo_sugerido,
                "criado_em": r.criado_em.isoformat() if r.criado_em else None,
            }
            for r in roteiros
        ]


async def atualizar_status_revisao(video_id: str, status: str) -> bool:
    """
    Atualiza o status de revisão de um roteiro.

    Args:
        video_id: ID do vídeo
        status: "aprovado" ou "rejeitado"

    Returns:
        True se atualizou, False se não encontrou
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(RoteiroDB).where(RoteiroDB.video_id == video_id)
        resultado = await session.execute(stmt)
        roteiro = resultado.scalar_one_or_none()

        if not roteiro:
            return False

        roteiro.status_revisao = status
        roteiro.revisado_em = dt.datetime.now(dt.timezone.utc)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# Operações de Ideias Manuais (Subfase 8.8)
# ---------------------------------------------------------------------------

async def salvar_ideia_manual(
    nicho: str,
    titulo_sugerido: str,
    descricao_breve: str | None = None,
    tendencia_relacionada: str | None = None,
    prioridade: str = "normal",
) -> int:
    """
    Salva uma ideia manual injetada pelo usuário.

    Args:
        nicho: Nicho do canal
        titulo_sugerido: Título da ideia
        descricao_breve: Descrição opcional
        tendencia_relacionada: Tendência que inspirou a ideia
        prioridade: "alta" ou "normal"

    Returns:
        ID da ideia criada
    """
    async with AsyncSessionLocal() as session:
        registro = IdeiaManual(
            nicho=nicho,
            titulo_sugerido=titulo_sugerido,
            descricao_breve=descricao_breve,
            tendencia_relacionada=tendencia_relacionada,
            prioridade=prioridade,
            status="pendente",
        )
        session.add(registro)
        await session.commit()
        await session.refresh(registro)
        return registro.id


async def buscar_ideias_manuais_pendentes(nicho: str) -> list[dict]:
    """
    Busca ideias manuais pendentes para um nicho.

    Args:
        nicho: Nicho do canal

    Returns:
        Lista de dicts com {id, titulo_sugerido, descricao_breve, tendencia_relacionada, prioridade}
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = (
            select(IdeiaManual)
            .where(
                IdeiaManual.nicho == nicho,
                IdeiaManual.status == "pendente",
            )
            .order_by(IdeiaManual.prioridade.desc(), IdeiaManual.criado_em.asc())
        )
        resultado = await session.execute(stmt)
        ideias = resultado.scalars().all()

        return [
            {
                "id": ideia.id,
                "titulo_sugerido": ideia.titulo_sugerido,
                "descricao_breve": ideia.descricao_breve,
                "tendencia_relacionada": ideia.tendencia_relacionada,
                "prioridade": ideia.prioridade,
            }
            for ideia in ideias
        ]


async def marcar_ideia_manual_usada(ideia_id: int, video_id: str) -> bool:
    """
    Marca uma ideia manual como usada, vinculando ao video_id.

    Args:
        ideia_id: ID da ideia manual
        video_id: ID do vídeo gerado

    Returns:
        True se atualizou, False se não encontrou
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(IdeiaManual).where(IdeiaManual.id == ideia_id)
        resultado = await session.execute(stmt)
        ideia = resultado.scalar_one_or_none()

        if not ideia:
            return False

        ideia.status = "usada"
        ideia.video_id = video_id
        await session.commit()
        return True


async def marcar_ideia_manual_descartada(ideia_id: int) -> bool:
    """
    Marca uma ideia manual como descartada.

    Args:
        ideia_id: ID da ideia manual

    Returns:
        True se atualizou, False se não encontrou
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(IdeiaManual).where(IdeiaManual.id == ideia_id)
        resultado = await session.execute(stmt)
        ideia = resultado.scalar_one_or_none()

        if not ideia:
            return False

        ideia.status = "descartada"
        await session.commit()
        return True


async def listar_ideias_manuais(
    nicho: str | None = None,
    status: str | None = None,
    limite: int = 50,
) -> list[dict]:
    """
    Lista ideias manuais com filtros opcionais.

    Args:
        nicho: Filtrar por nicho (opcional)
        status: Filtrar por status (opcional)
        limite: Número máximo de registros

    Returns:
        Lista de dicts com dados das ideias
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(IdeiaManual)

        if nicho:
            stmt = stmt.where(IdeiaManual.nicho == nicho)
        if status:
            stmt = stmt.where(IdeiaManual.status == status)

        stmt = stmt.order_by(IdeiaManual.criado_em.desc()).limit(limite)
        resultado = await session.execute(stmt)
        ideias = resultado.scalars().all()

        return [
            {
                "id": ideia.id,
                "nicho": ideia.nicho,
                "titulo_sugerido": ideia.titulo_sugerido,
                "descricao_breve": ideia.descricao_breve,
                "tendencia_relacionada": ideia.tendencia_relacionada,
                "prioridade": ideia.prioridade,
                "status": ideia.status,
                "video_id": ideia.video_id,
                "criado_em": ideia.criado_em.isoformat() if ideia.criado_em else None,
            }
            for ideia in ideias
        ]


async def buscar_ideia_manual_por_id(ideia_id: int) -> dict | None:
    """
    Busca uma ideia manual pelo ID.

    Args:
        ideia_id: ID da ideia

    Returns:
        Dict com dados da ideia ou None
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(IdeiaManual).where(IdeiaManual.id == ideia_id)
        resultado = await session.execute(stmt)
        ideia = resultado.scalar_one_or_none()

        if not ideia:
            return None

        return {
            "id": ideia.id,
            "nicho": ideia.nicho,
            "titulo_sugerido": ideia.titulo_sugerido,
            "descricao_breve": ideia.descricao_breve,
            "tendencia_relacionada": ideia.tendencia_relacionada,
            "prioridade": ideia.prioridade,
            "status": ideia.status,
            "video_id": ideia.video_id,
            "criado_em": ideia.criado_em.isoformat() if ideia.criado_em else None,
        }

class GameplaySegmento(Base):
    """
    Segmentos de gameplay processados e aprovados.

    Cada registro representa um segmento de vídeo curto (30s padrão)
    extraído de gravações brutas de sessões de jogo, com movimento
    validado (exclui menus, telas paradas, carregamentos).
    """
    __tablename__ = "gameplay_segmentos"
    __table_args__ = {"schema": "dados"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    jogo_origem: Mapped[str] = mapped_column(String, nullable=False, index=True)
    caminho_arquivo: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    duracao_segundos: Mapped[float] = mapped_column(Float, nullable=False)
    score_movimento: Mapped[float] = mapped_column(Float, nullable=False)
    faixa_intensidade: Mapped[str] = mapped_column(String, nullable=False)  # calmo, moderado, intenso
    hash_conteudo: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)  # MD5
    usado_em: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)  # video_ids
    criado_em: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


async def salvar_gameplay_segmentos(segmentos: list[dict]) -> list[str]:
    """
    Salva múltiplos segmentos de gameplay no banco.

    Args:
        segmentos: Lista de dicts com metadados dos segmentos

    Returns:
        Lista de IDs dos segmentos salvos
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        ids = []

        for seg_data in segmentos:
            # Verificar se hash já existe (dedup)
            stmt = select(GameplaySegmento).where(
                GameplaySegmento.hash_conteudo == seg_data["hash_conteudo"]
            )
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                logger.info(
                    "models.gameplay_duplicado",
                    extra={"hash": seg_data["hash_conteudo"][:12]},
                )
                ids.append(str(existing.id))
                continue

            # Criar novo registro
            segmento = GameplaySegmento(
                jogo_origem=seg_data["jogo_origem"],
                caminho_arquivo=seg_data["caminho_arquivo"],
                duracao_segundos=seg_data["duracao_segundos"],
                score_movimento=seg_data["score_movimento"],
                faixa_intensidade=seg_data["faixa_intensidade"],
                hash_conteudo=seg_data["hash_conteudo"],
                usado_em=[],
            )

            session.add(segmento)
            await session.flush()
            ids.append(str(segmento.id))

        await session.commit()

        logger.info(
            "models.gameplay_segmentos_salvos",
            extra={"total": len(ids)},
        )

        return ids


async def buscar_gameplay_segmentos(
    jogo: str | None = None,
    faixa_intensidade: str | None = None,
    min_score: float | None = None,
    limite: int = 100,
) -> list[dict]:
    """
    Busca segmentos de gameplay com filtros opcionais.

    Args:
        jogo: Filtrar por jogo
        faixa_intensidade: Filtrar por intensidade (calmo, moderado, intenso)
        min_score: Score mínimo de movimento
        limite: Máximo de resultados

    Returns:
        Lista de dicts com dados dos segmentos
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(GameplaySegmento).order_by(GameplaySegmento.score_movimento.desc())

        if jogo:
            stmt = stmt.where(GameplaySegmento.jogo_origem == jogo)
        if faixa_intensidade:
            stmt = stmt.where(GameplaySegmento.faixa_intensidade == faixa_intensidade)
        if min_score is not None:
            stmt = stmt.where(GameplaySegmento.score_movimento >= min_score)

        stmt = stmt.limit(limite)

        result = await session.execute(stmt)
        segmentos = result.scalars().all()

        return [
            {
                "id": seg.id,
                "jogo_origem": seg.jogo_origem,
                "caminho_arquivo": seg.caminho_arquivo,
                "duracao_segundos": seg.duracao_segundos,
                "score_movimento": seg.score_movimento,
                "faixa_intensidade": seg.faixa_intensidade,
                "usado_em": seg.usado_em or [],
                "criado_em": seg.criado_em.isoformat() if seg.criado_em else None,
            }
            for seg in segmentos
        ]


async def marcar_gameplay_usado(
    segmento_id: int,
    video_id: str,
    data_uso: str | None = None,
) -> bool:
    """
    Marca um segmento como usado em um vídeo.

    Args:
        segmento_id: ID do segmento
        video_id: ID do vídeo onde foi usado
        data_uso: Data de uso (YYYY-MM-DD), opcional

    Returns:
        True se atualizado com sucesso
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(GameplaySegmento).where(GameplaySegmento.id == segmento_id)
        result = await session.execute(stmt)
        segmento = result.scalar_one_or_none()

        if not segmento:
            return False

        if segmento.usado_em is None:
            segmento.usado_em = []

        # Formato: "video_id:YYYY-MM-DD"
        marca = f"{video_id}:{data_uso}" if data_uso else video_id

        if marca not in segmento.usado_em:
            segmento.usado_em = segmento.usado_em + [marca]

        await session.commit()
        return True


# ---------------------------------------------------------------------------
# Operações de Nichos (CRUD dinâmico)
# ---------------------------------------------------------------------------

async def salvar_nicho(
    nome: str,
    prompt_ideacao: str,
    prompt_roteiro_adicional: str,
    prompt_roteiro_short: str,
    categoria_google_trends: int,
    subreddits_sugeridos: list[str],
    gameplay_intensidade_preferida: str = "moderado",
    pitch_shift_semitons: float | None = None,
    velocidade_fala: float | None = None,
) -> str:
    """
    Salva um novo nicho no banco de dados.

    Args:
        nome: Nome único do nicho
        prompt_ideacao: Prompt para geração de ideias
        prompt_roteiro_adicional: Diretrizes adicionais para roteiro
        prompt_roteiro_short: Diretrizes para shorts
        categoria_google_trends: ID da categoria no Google Trends
        subreddits_sugeridos: Lista de subreddits para buscar tendências
        gameplay_intensidade_preferida: Intensidade preferida de gameplay
        pitch_shift_semitons: Variação de tom para TTS
        velocidade_fala: Velocidade de fala para TTS

    Returns:
        Nome do nicho criado
    """
    async with AsyncSessionLocal() as session:
        registro = Nicho(
            nome=nome,
            prompt_ideacao=prompt_ideacao,
            prompt_roteiro_adicional=prompt_roteiro_adicional,
            prompt_roteiro_short=prompt_roteiro_short,
            categoria_google_trends=categoria_google_trends,
            subreddits_sugeridos=subreddits_sugeridos,
            gameplay_intensidade_preferida=gameplay_intensidade_preferida,
            pitch_shift_semitons=pitch_shift_semitons,
            velocidade_fala=velocidade_fala,
            ativo=True,
        )
        session.add(registro)
        await session.commit()
        return nome


async def listar_nichos(apenas_ativos: bool = False) -> list[dict]:
    """
    Lista todos os nichos cadastrados.

    Args:
        apenas_ativos: Se True, retorna apenas nichos ativos

    Returns:
        Lista de dicts com dados dos nichos
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Nicho)

        if apenas_ativos:
            stmt = stmt.where(Nicho.ativo == True)

        stmt = stmt.order_by(Nicho.nome)
        result = await session.execute(stmt)
        nichos = result.scalars().all()

        return [
            {
                "id": nicho.id,
                "nome": nicho.nome,
                "prompt_ideacao": nicho.prompt_ideacao,
                "prompt_roteiro_adicional": nicho.prompt_roteiro_adicional,
                "prompt_roteiro_short": nicho.prompt_roteiro_short,
                "categoria_google_trends": nicho.categoria_google_trends,
                "subreddits_sugeridos": nicho.subreddits_sugeridos,
                "gameplay_intensidade_preferida": nicho.gameplay_intensidade_preferida,
                "pitch_shift_semitons": nicho.pitch_shift_semitons,
                "velocidade_fala": nicho.velocidade_fala,
                "ativo": nicho.ativo,
                "criado_em": nicho.criado_em.isoformat() if nicho.criado_em else None,
                "atualizado_em": nicho.atualizado_em.isoformat() if nicho.atualizado_em else None,
            }
            for nicho in nichos
        ]


async def buscar_nicho_por_nome(nome: str) -> dict | None:
    """
    Busca um nicho pelo nome.

    Args:
        nome: Nome do nicho

    Returns:
        Dict com dados do nicho ou None
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Nicho).where(Nicho.nome == nome)
        result = await session.execute(stmt)
        nicho = result.scalar_one_or_none()

        if not nicho:
            return None

        return {
            "id": nicho.id,
            "nome": nicho.nome,
            "prompt_ideacao": nicho.prompt_ideacao,
            "prompt_roteiro_adicional": nicho.prompt_roteiro_adicional,
            "prompt_roteiro_short": nicho.prompt_roteiro_short,
            "categoria_google_trends": nicho.categoria_google_trends,
            "subreddits_sugeridos": nicho.subreddits_sugeridos,
            "gameplay_intensidade_preferida": nicho.gameplay_intensidade_preferida,
            "pitch_shift_semitons": nicho.pitch_shift_semitons,
            "velocidade_fala": nicho.velocidade_fala,
            "ativo": nicho.ativo,
            "criado_em": nicho.criado_em.isoformat() if nicho.criado_em else None,
            "atualizado_em": nicho.atualizado_em.isoformat() if nicho.atualizado_em else None,
        }


async def atualizar_nicho(
    nome: str,
    prompt_ideacao: str | None = None,
    prompt_roteiro_adicional: str | None = None,
    prompt_roteiro_short: str | None = None,
    categoria_google_trends: int | None = None,
    subreddits_sugeridos: list[str] | None = None,
    gameplay_intensidade_preferida: str | None = None,
    pitch_shift_semitons: float | None = None,
    velocidade_fala: float | None = None,
    ativo: bool | None = None,
) -> bool:
    """
    Atualiza um nicho existente.

    Args:
        nome: Nome do nicho a atualizar
        Outros args: Campos a atualizar (None = manter atual)

    Returns:
        True se atualizou, False se não encontrou
    """
    from sqlalchemy import select

    async with AsyncSessionLocal() as session:
        stmt = select(Nicho).where(Nicho.nome == nome)
        result = await session.execute(stmt)
        nicho = result.scalar_one_or_none()

        if not nicho:
            return False

        if prompt_ideacao is not None:
            nicho.prompt_ideacao = prompt_ideacao
        if prompt_roteiro_adicional is not None:
            nicho.prompt_roteiro_adicional = prompt_roteiro_adicional
        if prompt_roteiro_short is not None:
            nicho.prompt_roteiro_short = prompt_roteiro_short
        if categoria_google_trends is not None:
            nicho.categoria_google_trends = categoria_google_trends
        if subreddits_sugeridos is not None:
            nicho.subreddits_sugeridos = subreddits_sugeridos
        if gameplay_intensidade_preferida is not None:
            nicho.gameplay_intensidade_preferida = gameplay_intensidade_preferida
        if pitch_shift_semitons is not None:
            nicho.pitch_shift_semitons = pitch_shift_semitons
        if velocidade_fala is not None:
            nicho.velocidade_fala = velocidade_fala
        if ativo is not None:
            nicho.ativo = ativo

        await session.commit()
        return True


async def deletar_nicho(nome: str) -> bool:
    """
    Remove um nicho (soft delete - marca como inativo).

    Args:
        nome: Nome do nicho

    Returns:
        True se desativou, False se não encontrou
    """
    return await atualizar_nicho(nome, ativo=False)
