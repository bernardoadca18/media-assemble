"""
Testes da Subfase 8.1 — Rastreabilidade e observabilidade.

Cobertura:
- Persistência de execução com motivo_falha
- Endpoints FastAPI de consulta
- Propagação de video_id nos logs
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def client():
    """Cliente síncrono para testes de API."""
    from api.status import app
    return TestClient(app)


# ============================================================================
# Testes de persistência com motivo_falha (com mocks)
# ============================================================================

@pytest.mark.asyncio
async def test_salvar_execucao_com_motivo_falha():
    """Persistência de execução falha deve incluir motivo_falha."""
    from db.models import salvar_execucao, ExecucaoPipeline

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with patch("db.models.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        await salvar_execucao(
            video_id="test-video-falha-001",
            nicho="tecnologia",
            etapa_atual="audio",
            sucesso=False,
            motivo_falha="ValueError: Audio file not found",
        )

        mock_session.add.assert_called_once()
        registro = mock_session.add.call_args[0][0]
        assert isinstance(registro, ExecucaoPipeline)
        assert registro.video_id == "test-video-falha-001"
        assert registro.nicho == "tecnologia"
        assert registro.etapa_atual == "audio"
        assert registro.sucesso is False
        assert registro.motivo_falha == "ValueError: Audio file not found"


@pytest.mark.asyncio
async def test_salvar_execucao_sucesso_sem_motivo_falha():
    """Persistência de execução bem-sucedida não deve ter motivo_falha."""
    from db.models import salvar_execucao, ExecucaoPipeline

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = mock_result

    with patch("db.models.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        await salvar_execucao(
            video_id="test-video-sucesso-001",
            nicho="cultura_pop",
            etapa_atual="renderizacao",
            sucesso=True,
            caminho_video_final="/videos/test-video-sucesso-001.mp4",
            wer_medio=0.03,
        )

        mock_session.add.assert_called_once()
        registro = mock_session.add.call_args[0][0]
        assert isinstance(registro, ExecucaoPipeline)
        assert registro.sucesso is True
        assert registro.motivo_falha is None
        assert registro.caminho_video_final == "/videos/test-video-sucesso-001.mp4"
        assert registro.wer_medio == 0.03


@pytest.mark.asyncio
async def test_atualizar_execucao_com_motivo_falha():
    """Atualização de execução existente deve atualizar motivo_falha."""
    from db.models import salvar_execucao, ExecucaoPipeline

    mock_session = AsyncMock()

    # Simular registro existente
    registro_existente = ExecucaoPipeline(
        id=1,
        video_id="test-video-update-001",
        nicho="futebol",
        etapa_atual="ideacao",
        sucesso=False,
        motivo_falha="Initial error",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = registro_existente
    mock_session.execute.return_value = mock_result

    with patch("db.models.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        await salvar_execucao(
            video_id="test-video-update-001",
            nicho="futebol",
            etapa_atual="roteirizacao",
            sucesso=False,
            motivo_falha="Updated error message",
        )

        # Verificar que o registro foi atualizado (não criado novo)
        mock_session.add.assert_not_called()
        assert registro_existente.etapa_atual == "roteirizacao"
        assert registro_existente.motivo_falha == "Updated error message"


# ============================================================================
# Testes de endpoints FastAPI (com mocks)
# ============================================================================

def test_endpoint_listar_execucoes_com_filtro_nicho(client):
    """GET /execucoes deve filtrar por nicho corretamente."""
    # Mock do banco de dados
    mock_execucoes = [
        MagicMock(
            video_id="test-001",
            nicho="tecnologia",
            etapa_atual="audio",
            sucesso=False,
            motivo_falha="Test error",
            criado_em=datetime(2026, 8, 8, 12, 0, 0),
        )
    ]

    with patch("api.status.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_execucoes
        mock_session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        response = client.get("/execucoes?nicho=tecnologia&limite=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["nicho"] == "tecnologia"


def test_endpoint_listar_execucoes_com_filtro_status(client):
    """GET /execucoes deve filtrar por status corretamente."""
    mock_execucoes = [
        MagicMock(
            video_id="test-002",
            nicho="cultura_pop",
            etapa_atual="assets",
            sucesso=False,
            motivo_falha="Asset not found",
            criado_em=datetime(2026, 8, 8, 12, 0, 0),
        )
    ]

    with patch("api.status.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_execucoes
        mock_session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        response = client.get("/execucoes?status=falha&limite=10")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["sucesso"] is False


def test_endpoint_obter_execucao_existente(client):
    """GET /execucoes/{video_id} deve retornar detalhes completos."""
    mock_execucao = MagicMock(
        video_id="test-api-detail-001",
        nicho="cultura_pop",
        etapa_atual="renderizacao",
        sucesso=False,
        caminho_video_final=None,
        wer_medio=None,
        motivo_falha="Test API error",
        criado_em=datetime(2026, 8, 8, 12, 0, 0),
    )

    with patch("api.status.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_execucao
        mock_session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        response = client.get("/execucoes/test-api-detail-001")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "test-api-detail-001"
        assert data["nicho"] == "cultura_pop"
        assert data["etapa_atual"] == "renderizacao"
        assert data["sucesso"] is False
        assert data["motivo_falha"] == "Test API error"


def test_endpoint_obter_execucao_inexistente(client):
    """GET /execucoes/{video_id} deve retornar 404 se não existir."""
    with patch("api.status.AsyncSessionLocal") as mock_session_factory:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        response = client.get("/execucoes/video-inexistente-xyz")

        assert response.status_code == 404
        assert "não encontrada" in response.json()["detail"]


def test_endpoint_health_check(client):
    """GET /health deve retornar status ok."""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


# ============================================================================
# Testes de propagação de video_id nos logs
# ============================================================================

def test_set_video_id_no_contexto():
    """set_video_id deve definir video_id no contexto."""
    from utils.logger import set_video_id, get_video_id

    set_video_id("test-video-log-001")
    assert get_video_id() == "test-video-log-001"

    set_video_id(None)
    assert get_video_id() is None


def test_video_id_filter_injeta_id_no_log_record():
    """VideoIdFilter deve injetar video_id no LogRecord."""
    import logging
    from utils.logger import VideoIdFilter, set_video_id

    # Definir video_id no contexto
    set_video_id("test-video-filter-001")

    # Criar filtro e record de teste
    filtro = VideoIdFilter()
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="test message",
        args=(),
        exc_info=None,
    )

    # Aplicar filtro
    filtro.filter(record)

    assert hasattr(record, "video_id")
    assert record.video_id == "test-video-filter-001"

    # Limpar contexto
    set_video_id(None)


# ============================================================================
# Testes de listar_execucoes_falhas com motivo_falha
# ============================================================================

@pytest.mark.asyncio
async def test_listar_execucoes_falhas_inclui_motivo():
    """listar_execucoes_falhas deve incluir motivo_falha no retorno."""
    from db.models import listar_execucoes_falhas, ExecucaoPipeline

    mock_execucoes = [
        ExecucaoPipeline(
            id=1,
            video_id="test-list-falhas-001",
            nicho="tecnologia",
            etapa_atual="assets",
            sucesso=False,
            motivo_falha="PexelsAPIError: Rate limit exceeded",
            criado_em=datetime(2026, 8, 8, 12, 0, 0),
        )
    ]

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_execucoes
    mock_session.execute.return_value = mock_result

    with patch("db.models.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        falhas = await listar_execucoes_falhas(limite=50)

        assert len(falhas) == 1
        assert falhas[0]["video_id"] == "test-list-falhas-001"
        assert falhas[0]["motivo_falha"] == "PexelsAPIError: Rate limit exceeded"
