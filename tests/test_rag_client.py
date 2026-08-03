"""Testes para persistência no banco de dados."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession


class TestBuscarTitulosRecentes:
    """Testes para busca de títulos recentes."""

    @pytest.mark.asyncio
    async def test_buscar_titulos_sucesso(self):
        """Testa busca de títulos com banco mockado."""
        titulos_esperados = ["Vídeo 1", "Vídeo 2", "Vídeo 3"]

        with patch("services.ideation.rag_client.buscar_titulos_recentes_db", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = titulos_esperados

            from services.ideation.rag_client import buscar_titulos_recentes
            resultado = await buscar_titulos_recentes("cultura_pop", limite=10)

            assert resultado == titulos_esperados
            mock_db.assert_called_once_with(nicho="cultura_pop", limite=10)

    @pytest.mark.asyncio
    async def test_buscar_titulos_erro_banco(self):
        """Testa tratamento de erro quando banco falha."""
        with patch("services.ideation.rag_client.buscar_titulos_recentes_db", new_callable=AsyncMock) as mock_db:
            mock_db.side_effect = Exception("Erro de conexão")

            from services.ideation.rag_client import buscar_titulos_recentes
            resultado = await buscar_titulos_recentes("cultura_pop")

            # Em caso de erro, retorna lista vazia
            assert resultado == []

    @pytest.mark.asyncio
    async def test_buscar_titulos_lista_vazia(self):
        """Testa retorno quando não há títulos no banco."""
        with patch("services.ideation.rag_client.buscar_titulos_recentes_db", new_callable=AsyncMock) as mock_db:
            mock_db.return_value = []

            from services.ideation.rag_client import buscar_titulos_recentes
            resultado = await buscar_titulos_recentes("cultura_pop")

            assert resultado == []


class TestSalvarIdeias:
    """Testes para persistência de ideias."""

    @pytest.mark.asyncio
    async def test_salvar_ideias_sucesso(self):
        """Testa salvamento de ideias no banco."""
        from pipeline.schemas import Ideia

        ideias = [
            Ideia(topico="Teste1", titulo_sugerido="Título 1", descricao_breve="Desc 1"),
            Ideia(topico="Teste2", titulo_sugerido="Título 2", descricao_breve="Desc 2"),
        ]

        with patch("db.models.AsyncSessionLocal") as mock_session_factory:
            mock_session = AsyncMock(spec=AsyncSession)
            mock_session.__aenter__.return_value = mock_session
            mock_session.__aexit__.return_value = None
            mock_session_factory.return_value = mock_session

            mock_execute = AsyncMock()
            mock_session.execute = mock_execute
            mock_session.commit = AsyncMock()

            from db.models import salvar_ideias
            await salvar_ideias(ideias)

            # Verifica que commit foi chamado
            mock_session.commit.assert_called_once()
