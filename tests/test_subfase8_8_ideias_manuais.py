"""
Testes para Subfase 8.8 — Painel de controle editorial.

Valida:
- Tabela dados.ideias_manuais
- CRUD de ideias manuais
- Prioridade alta substituindo vagas do LLM
- Prioridade normal como contexto adicional
- Marcação de status (usada/descartada)
- CLI commands
- API endpoints
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pipeline.schemas import Ideia
from db.models import IdeiaManual


class TestSchemaIdeiaManualId:
    """Testa campo ideia_manual_id no schema Ideia."""

    def test_ideia_sem_ideia_manual_id(self):
        """Ideia sem origem manual."""
        ideia = Ideia(
            topico="Teste",
            titulo_sugerido="Título Teste",
            descricao_breve="Descrição teste",
            justificativa="Teste",
            potencial_viral=8.0,
        )
        assert ideia.ideia_manual_id is None

    def test_ideia_com_ideia_manual_id(self):
        """Ideia com origem manual."""
        ideia = Ideia(
            topico="Teste",
            titulo_sugerido="Título Teste",
            descricao_breve="Descrição teste",
            justificativa="Teste",
            potencial_viral=8.0,
            ideia_manual_id=42,
        )
        assert ideia.ideia_manual_id == 42


class TestOperacoesDBIdeiasManuais:
    """Testa operações de banco para ideias manuais."""

    @pytest.mark.asyncio
    async def test_salvar_ideia_manual(self):
        """Salva uma ideia manual no banco."""
        from db.models import salvar_ideia_manual

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            ideia = MagicMock()
            ideia.id = 1
            mock_session_instance.refresh = AsyncMock()

            with patch("db.models.IdeiaManual", return_value=ideia):
                ideia_id = await salvar_ideia_manual(
                    nicho="cultura_pop",
                    titulo_sugerido="Minha Ideia",
                    descricao_breve="Descrição",
                    prioridade="alta",
                )

            assert ideia_id == 1
            mock_session_instance.add.assert_called_once()
            mock_session_instance.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_buscar_ideias_manuais_pendentes(self):
        """Busca ideias manuais pendentes por nicho."""
        from db.models import buscar_ideias_manuais_pendentes

        mock_ideias = [
            MagicMock(
                id=1,
                titulo_sugerido="Ideia 1",
                descricao_breve="Desc 1",
                tendencia_relacionada=None,
                prioridade="alta",
            ),
            MagicMock(
                id=2,
                titulo_sugerido="Ideia 2",
                descricao_breve="Desc 2",
                tendencia_relacionada="Tendência X",
                prioridade="normal",
            ),
        ]

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = mock_ideias
            mock_session_instance.execute.return_value = mock_result

            ideias = await buscar_ideias_manuais_pendentes("cultura_pop")

        assert len(ideias) == 2
        assert ideias[0]["prioridade"] == "alta"
        assert ideias[1]["prioridade"] == "normal"

    @pytest.mark.asyncio
    async def test_marcar_ideia_manual_usada(self):
        """Marca ideia como usada vinculando ao video_id."""
        from db.models import marcar_ideia_manual_usada

        mock_ideia = MagicMock()
        mock_ideia.id = 1

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_ideia
            mock_session_instance.execute.return_value = mock_result

            sucesso = await marcar_ideia_manual_usada(1, "video_123")

        assert sucesso is True
        assert mock_ideia.status == "usada"
        assert mock_ideia.video_id == "video_123"
        mock_session_instance.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_marcar_ideia_manual_descartada(self):
        """Marca ideia como descartada."""
        from db.models import marcar_ideia_manual_descartada

        mock_ideia = MagicMock()
        mock_ideia.id = 1

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_ideia
            mock_session_instance.execute.return_value = mock_result

            sucesso = await marcar_ideia_manual_descartada(1)

        assert sucesso is True
        assert mock_ideia.status == "descartada"


class TestIntegracaoIdeationAgent:
    """Testa integração de ideias manuais no agente de ideação."""

    @pytest.mark.asyncio
    async def test_ideias_manuais_alta_prioridade_substituem_llm(self):
        """Ideias de alta prioridade substituem vagas do LLM."""
        from services.ideation.agent import gerar_ideias

        # Mock de ideias manuais pendentes
        mock_ideias_manuais = [
            {
                "id": 1,
                "titulo_sugerido": "Ideia Manual Alta",
                "descricao_breve": "Descrição manual",
                "tendencia_relacionada": None,
                "prioridade": "alta",
            }
        ]

        # Mock de resposta do LLM
        mock_resposta_llm = {
            "ideias": [
                {"topico": "T1", "titulo_sugerido": "LLM 1", "descricao_breve": "D1", "justificativa": "J1", "potencial_viral": 7.0},
                {"topico": "T2", "titulo_sugerido": "LLM 2", "descricao_breve": "D2", "justificativa": "J2", "potencial_viral": 7.0},
                {"topico": "T3", "titulo_sugerido": "LLM 3", "descricao_breve": "D3", "justificativa": "J3", "potencial_viral": 7.0},
                {"topico": "T4", "titulo_sugerido": "LLM 4", "descricao_breve": "D4", "justificativa": "J4", "potencial_viral": 7.0},
                {"topico": "T5", "titulo_sugerido": "LLM 5", "descricao_breve": "D5", "justificativa": "J5", "potencial_viral": 7.0},
            ]
        }

        with patch("db.models.buscar_ideias_manuais_pendentes", new_callable=AsyncMock, return_value=mock_ideias_manuais):
            with patch("services.ideation.rag_client.buscar_titulos_recentes", new_callable=AsyncMock, return_value=[]):
                with patch("services.ideation.agent.complete_cloud", new_callable=AsyncMock) as mock_llm:
                    import json
                    mock_llm.return_value = json.dumps(mock_resposta_llm)
                    with patch("services.ideation.rag_client.checar_duplicidade_semantica", return_value=False):
                        with patch("db.models.salvar_ideias", new_callable=AsyncMock):
                            ideias = await gerar_ideias("cultura_pop", ["tendencia1"])

        # A ideia manual de alta prioridade deve estar na lista
        titulos = [i.titulo_sugerido for i in ideias]
        assert "Ideia Manual Alta" in titulos
        # Deve ter pelo menos uma ideia com ideia_manual_id
        ideias_manuais = [i for i in ideias if i.ideia_manual_id is not None]
        assert len(ideias_manuais) == 1

    @pytest.mark.asyncio
    async def test_ideias_manuais_prioridade_normal_como_contexto(self):
        """Ideias de prioridade normal entram como contexto no prompt."""
        # Este teste verifica que o código integra ideias manuais de prioridade normal
        # A verificação real do prompt é feita por testes de integração
        # Aqui apenas confirmamos que a função não falha ao processar ideias manuais
        from services.ideation.agent import gerar_ideias

        mock_ideias_manuais = [
            {
                "id": 2,
                "titulo_sugerido": "Ideia Normal",
                "descricao_breve": "Contexto adicional",
                "tendencia_relacionada": None,
                "prioridade": "normal",
            }
        ]

        mock_resposta_llm = {
            "ideias": [
                {"topico": "T1", "titulo_sugerido": "LLM 1", "descricao_breve": "D1", "justificativa": "J1", "potencial_viral": 7.0},
                {"topico": "T2", "titulo_sugerido": "LLM 2", "descricao_breve": "D2", "justificativa": "J2", "potencial_viral": 7.0},
                {"topico": "T3", "titulo_sugerido": "LLM 3", "descricao_breve": "D3", "justificativa": "J3", "potencial_viral": 7.0},
                {"topico": "T4", "titulo_sugerido": "LLM 4", "descricao_breve": "D4", "justificativa": "J4", "potencial_viral": 7.0},
                {"topico": "T5", "titulo_sugerido": "LLM 5", "descricao_breve": "D5", "justificativa": "J5", "potencial_viral": 7.0},
            ]
        }

        with patch("db.models.buscar_ideias_manuais_pendentes", new_callable=AsyncMock, return_value=mock_ideias_manuais):
            with patch("services.ideation.rag_client.buscar_titulos_recentes", new_callable=AsyncMock, return_value=[]):
                with patch("services.ideation.agent.complete_cloud", new_callable=AsyncMock) as mock_llm:
                    import json
                    mock_llm.return_value = json.dumps(mock_resposta_llm)
                    with patch("services.ideation.rag_client.checar_duplicidade_semantica", return_value=False):
                        with patch("db.models.salvar_ideias", new_callable=AsyncMock):
                            ideias = await gerar_ideias("cultura_pop", ["tendencia1"])

        # Verificar que o código executou sem erros
        assert len(ideias) == 5
        # Ideias de prioridade normal são adicionadas como contexto, não substituem
        # Então todas as ideias LLM devem estar presentes
        titulos = [i.titulo_sugerido for i in ideias]
        assert "LLM 1" in titulos


class TestCLICommands:
    """Testa comandos CLI para ideias manuais."""

    def test_sugerir_ideia_cli(self):
        """Testa comando --sugerir-ideia."""
        from main import _sugerir_ideia
        import asyncio

        with patch("db.models.salvar_ideia_manual", new_callable=AsyncMock, return_value=1):
            asyncio.run(_sugerir_ideia("cultura_pop", "Minha Ideia", "Descrição", "alta"))

    def test_listar_ideias_manuais_cli(self):
        """Testa comando --listar-ideias-manuais."""
        from main import _listar_ideias_manuais
        import asyncio

        mock_ideias = [
            {
                "id": 1,
                "nicho": "cultura_pop",
                "titulo_sugerido": "Ideia Teste",
                "prioridade": "alta",
                "status": "pendente",
            }
        ]

        with patch("db.models.listar_ideias_manuais", new_callable=AsyncMock, return_value=mock_ideias):
            asyncio.run(_listar_ideias_manuais(None))

    def test_descartar_ideia_cli(self):
        """Testa comando --descartar-ideia."""
        from main import _descartar_ideia
        import asyncio

        with patch("db.models.marcar_ideia_manual_descartada", new_callable=AsyncMock, return_value=True):
            asyncio.run(_descartar_ideia(1))


class TestAPIEndpoints:
    """Testa endpoints da API para ideias manuais."""

    @pytest.mark.asyncio
    async def test_post_ideias_manuais(self):
        """Testa POST /ideias-manuais."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        mock_ideia_criada = {
            "id": 1,
            "nicho": "cultura_pop",
            "titulo_sugerido": "Minha Ideia",
            "descricao_breve": "Descrição",
            "tendencia_relacionada": None,
            "prioridade": "alta",
            "status": "pendente",
            "video_id": None,
            "criado_em": "2026-08-08T12:00:00",
        }

        with patch("db.models.salvar_ideia_manual", new_callable=AsyncMock, return_value=1):
            with patch("db.models.buscar_ideia_manual_por_id", new_callable=AsyncMock, return_value=mock_ideia_criada):
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                    response = await client.post(
                        "/ideias-manuais",
                        json={
                            "nicho": "cultura_pop",
                            "titulo_sugerido": "Minha Ideia",
                            "prioridade": "alta",
                        }
                    )

        assert response.status_code == 201
        data = response.json()
        assert data["titulo_sugerido"] == "Minha Ideia"
        assert data["prioridade"] == "alta"

    @pytest.mark.asyncio
    async def test_get_ideias_manuais(self):
        """Testa GET /ideias-manuais."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        mock_ideias = [
            {
                "id": 1,
                "nicho": "cultura_pop",
                "titulo_sugerido": "Ideia 1",
                "descricao_breve": None,
                "tendencia_relacionada": None,
                "prioridade": "normal",
                "status": "pendente",
                "video_id": None,
                "criado_em": "2026-08-08T12:00:00",
            }
        ]

        with patch("db.models.listar_ideias_manuais", new_callable=AsyncMock, return_value=mock_ideias):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/ideias-manuais")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["titulo_sugerido"] == "Ideia 1"

    @pytest.mark.asyncio
    async def test_delete_ideias_manuais(self):
        """Testa DELETE /ideias-manuais/{id}."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        with patch("db.models.marcar_ideia_manual_descartada", new_callable=AsyncMock, return_value=True):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.delete("/ideias-manuais/1")

        assert response.status_code == 200
        assert "descartada" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_delete_ideias_manuais_nao_encontrada(self):
        """Testa DELETE com ID inexistente."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        with patch("db.models.marcar_ideia_manual_descartada", new_callable=AsyncMock, return_value=False):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.delete("/ideias-manuais/999")

        assert response.status_code == 404


class TestFluxoCompleto:
    """Testa fluxo completo de ideia manual."""

    @pytest.mark.asyncio
    async def test_ideia_manual_vira_video(self):
        """Ideia manual de alta prioridade vira vídeo e é marcada como usada."""
        from pipeline.orchestrator import rodar_etapa_roteirizacao
        from pipeline.schemas import Ideia

        ideia_manual = Ideia(
            topico="Ideia Manual",
            titulo_sugerido="Meu Vídeo Especial",
            descricao_breve="Descrição da ideia",
            justificativa="Ideia manual do usuário",
            potencial_viral=8.0,
            nicho="cultura_pop",
            ideia_manual_id=42,
        )

        mock_roteiro = MagicMock()
        mock_roteiro.metadata.video_id = "video_123"
        mock_roteiro.cenas = []
        mock_roteiro.metadata.duracao_estimada_segundos = 60.0

        with patch("pipeline.orchestrator.gerar_roteiro", new_callable=AsyncMock, return_value=mock_roteiro):
            with patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock, return_value="video_123"):
                with patch("db.models.marcar_ideia_manual_usada", new_callable=AsyncMock, return_value=True) as mock_marcar:
                    roteiro = await rodar_etapa_roteirizacao(ideia_manual, "cultura_pop")

                    # Verificar que marcar_ideia_manual_usada foi chamado
                    mock_marcar.assert_called_once_with(42, "video_123")

        assert roteiro is not None
