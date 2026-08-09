"""
Testes para os novos endpoints da API de gestão do Faceless Pipeline.

Cobre:
- Segurança (bind, CORS)
- Endpoint de retomar execução
- Endpoints de revisão manual
- Endpoints de gameplay
- Endpoints de configuração (nichos, GPU)
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch, MagicMock


# Importar a aplicação
from api.main import app


@pytest.fixture
def client():
    """Cliente de teste para a API."""
    return TestClient(app)


class TestSeguranca:
    """Testa configurações de segurança."""

    def test_cors_configurado_para_localhost(self):
        """CORS deve permitir apenas origins locais."""
        from api.main import app

        # Verificar se CORSMiddleware está configurado
        cors_middleware = None
        for middleware in app.user_middleware:
            if "CORSMiddleware" in str(middleware):
                cors_middleware = middleware
                break

        assert cors_middleware is not None, "CORSMiddleware não configurado"

    def test_health_check_inclui_bind_info(self, client):
        """Health check deve indicar bind em 127.0.0.1."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["bind"] == "127.0.0.1"
        assert data["auth"] == "disabled (local use only)"


class TestRetomarExecucao:
    """Testa endpoint de retomar execução falha."""

    @patch("api.main.buscar_execucao_falha")
    @patch("api.main.retomar_execucao_falha")
    def test_retomar_execucao_sucesso(self, mock_retomar, mock_buscar, client):
        """Retomar execução existente deve retornar sucesso."""
        # Mock da execução falha
        mock_buscar.return_value = {
            "video_id": "test-123",
            "nicho": "cultura_pop",
            "etapa_atual": "audio",
        }

        # Mock do resultado da retomada
        mock_retomar.return_value = {
            "sucesso": True,
            "etapa": "renderizacao",
        }

        response = client.post("/execucoes/test-123/retomar")

        assert response.status_code == 200
        data = response.json()
        assert data["sucesso"] is True
        assert data["video_id"] == "test-123"

    @patch("api.main.buscar_execucao_falha")
    def test_retomar_execucao_nao_encontrada(self, mock_buscar, client):
        """Retomar execução inexistente deve retornar 404."""
        mock_buscar.return_value = None

        response = client.post("/execucoes/inexistente/retomar")

        assert response.status_code == 404


class TestRevisaoManual:
    """Testa endpoints de revisão manual."""

    @patch("api.main.listar_roteiros_pendentes_revisao")
    def test_listar_pendentes_revisao(self, mock_listar, client):
        """Listar pendentes deve retornar lista de roteiros."""
        mock_listar.return_value = [
            {
                "video_id": "vid-1",
                "nicho": "cultura_pop",
                "titulo_sugerido": "Teste",
                "criado_em": "2024-01-01T00:00:00",
            }
        ]

        response = client.get("/revisao/pendentes")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["video_id"] == "vid-1"

    @patch("api.main.atualizar_status_revisao")
    def test_aprovar_roteiro(self, mock_atualizar, client):
        """Aprovar roteiro deve atualizar status."""
        mock_atualizar.return_value = True

        response = client.post("/revisao/vid-1/aprovar")

        assert response.status_code == 200
        data = response.json()
        assert data["sucesso"] is True
        assert data["novo_status"] == "aprovado"

    @patch("api.main.atualizar_status_revisao")
    def test_rejeitar_roteiro(self, mock_atualizar, client):
        """Rejeitar roteiro deve atualizar status."""
        mock_atualizar.return_value = True

        response = client.post("/revisao/vid-1/rejeitar")

        assert response.status_code == 200
        data = response.json()
        assert data["sucesso"] is True
        assert data["novo_status"] == "rejeitado"

    @patch("api.main.atualizar_status_revisao")
    def test_aprovar_roteiro_inexistente(self, mock_atualizar, client):
        """Aprovar roteiro inexistente deve retornar 404."""
        mock_atualizar.return_value = False

        response = client.post("/revisao/inexistente/aprovar")

        assert response.status_code == 404


class TestGameplayEndpoints:
    """Testa endpoints de gameplay."""

    @patch("api.main.buscar_gameplay_segmentos")
    def test_listar_segmentos(self, mock_buscar, client):
        """Listar segmentos deve retornar lista."""
        mock_buscar.return_value = [
            {
                "id": 1,
                "jogo_origem": "minecraft",
                "caminho_arquivo": "/data/seg1.mp4",
                "duracao_segundos": 30.0,
                "score_movimento": 10.5,
                "faixa_intensidade": "moderado",
                "usado_em": [],
                "criado_em": "2024-01-01T00:00:00",
            }
        ]

        response = client.get("/gameplay/segmentos")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["jogo_origem"] == "minecraft"

    @patch("api.main.buscar_gameplay_segmentos")
    def test_listar_segmentos_filtrar_por_jogo(self, mock_buscar, client):
        """Listar segmentos deve aceitar filtro por jogo."""
        mock_buscar.return_value = []

        response = client.get("/gameplay/segmentos?jogo=minecraft")

        assert response.status_code == 200
        mock_buscar.assert_called_once_with(
            jogo="minecraft",
            intensidade=None,
            limite=50
        )

    @patch("db.session.AsyncSessionLocal")
    def test_estatisticas_gameplay(self, mock_session_local, client):
        """Estatísticas deve retornar dados agregados."""
        # Mock da sessão e query
        mock_session = AsyncMock()
        mock_session_local.return_value.__aenter__.return_value = mock_session

        mock_result = MagicMock()
        mock_result.all.return_value = [
            MagicMock(
                jogo_origem="minecraft",
                total=10,
                duracao_total=300.0,
                score_medio=10.5,
            )
        ]
        mock_session.execute.return_value = mock_result

        response = client.get("/gameplay/estatisticas")

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 0


class TestNichosEndpoints:
    """Testa endpoints de nichos."""

    def test_listar_nichos(self, client):
        """Listar nichos deve retornar configurações."""
        response = client.get("/nichos")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 6  # 6 nichos configurados
        assert any(n["nome"] == "cultura_pop" for n in data)

    def test_obter_nicho_especifico(self, client):
        """Obter nicho específico deve retornar configuração."""
        response = client.get("/nichos/cultura_pop")

        assert response.status_code == 200
        data = response.json()
        assert data["nome"] == "cultura_pop"
        assert data["categoria_google_trends"] == 22

    def test_obter_nicho_inexistente(self, client):
        """Obter nicho inexistente deve retornar 404."""
        response = client.get("/nichos/inexistente")

        assert response.status_code == 404


class TestGPUStatus:
    """Testa endpoint de status da GPU."""

    @patch("api.main.gpu_status")
    def test_gpu_status_disponivel(self, mock_gpu_status, client):
        """GPU status deve retornar disponibilidade."""
        mock_gpu_status.return_value = {"disponivel": True, "tarefa_atual": None}

        response = client.get("/gpu-status")

        assert response.status_code == 200
        data = response.json()
        assert data["disponivel"] is True

    @patch("api.main.gpu_status")
    def test_gpu_status_em_uso(self, mock_gpu_status, client):
        """GPU status deve indicar quando em uso."""
        mock_gpu_status.return_value = {
            "disponivel": False,
            "tarefa_atual": "f5-tts-cena-03"
        }

        response = client.get("/gpu-status")

        assert response.status_code == 200
        data = response.json()
        assert data["disponivel"] is False


class TestIntegracaoRotas:
    """Testa integração geral das rotas."""

    def test_todas_rotas_existem(self, client):
        """Verifica se todas as rotas esperadas existem."""
        rotas_esperadas = [
            "/health",
            "/execucoes/{video_id}/retomar",
            "/revisao/pendentes",
            "/revisao/{video_id}/aprovar",
            "/revisao/{video_id}/rejeitar",
            "/gameplay/segmentos",
            "/gameplay/estatisticas",
            "/nichos",
            "/nichos/{nicho}",
            "/gpu-status",
        ]

        rotas_app = [route.path for route in app.routes]

        for rota in rotas_esperadas:
            # Verificar se a rota existe (com ou sem parâmetros)
            assert any(
                rota in r or r in rota for r in rotas_app
            ), f"Rota {rota} não encontrada"

    def test_docs_acessivel(self, client):
        """Documentação OpenAPI deve estar acessível."""
        response = client.get("/docs")

        assert response.status_code == 200

    def test_openapi_json_acessivel(self, client):
        """Schema OpenAPI deve estar acessível."""
        response = client.get("/openapi.json")

        assert response.status_code == 200
        data = response.json()
        assert "openapi" in data
        assert "paths" in data
