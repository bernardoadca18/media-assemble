"""Testes para o orquestrador do pipeline."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pipeline.schemas import Ideia
from pipeline.orchestrator import rodar_etapa_ideacao


class TestRodarEtapaIdeacao:
    """Testes para o fluxo de ideação ponta-a-ponta."""

    @pytest.mark.asyncio
    async def test_fluxo_ideacao_completo(self):
        """Testa o fluxo completo de coleta -> normalização -> ideação -> persistência."""
        ideias_mock = [
            Ideia(topico="Naruto", titulo_sugerido="Os Clãs Mais Poderosos de Naruto", descricao_breve="Análise"),
            Ideia(topico="One Piece", titulo_sugerido="Os Frutos do Diabo Mais Raros", descricao_breve="Lore"),
            Ideia(topico="Elden Ring", titulo_sugerido="A História Secreta das Terras Interas", descricao_breve="Lore profunda"),
            Ideia(topico="Universo DC", titulo_sugerido="Os Heróis Mais Trágicos da DC", descricao_breve="Análise"),
            Ideia(topico="Star Wars", titulo_sugerido="Os Sith Mais Poderosos da História", descricao_breve="Lore"),
        ]

        with patch("pipeline.orchestrator.coletar_tendencias", new_callable=AsyncMock) as mock_coletar, \
             patch("pipeline.orchestrator.normalizar_tendencias", new_callable=AsyncMock) as mock_normalizar, \
             patch("pipeline.orchestrator.gerar_ideias", new_callable=AsyncMock) as mock_ideias, \
             patch("pipeline.orchestrator.salvar_ideias", new_callable=AsyncMock) as mock_salvar:

            mock_coletar.return_value = ["Naruto", "One Piece", "Elden Ring"]
            mock_normalizar.return_value = ["Naruto", "One Piece", "Elden Ring"]
            mock_ideias.return_value = ideias_mock
            mock_salvar.return_value = None

            resultado = await rodar_etapa_ideacao("cultura_pop")

            assert len(resultado) == 5
            mock_coletar.assert_called_once_with("cultura_pop")
            mock_normalizar.assert_called_once()
            mock_ideias.assert_called_once()
            mock_salvar.assert_called_once()

    @pytest.mark.asyncio
    async def test_fluxo_sem_tendencias(self):
        """Testa comportamento quando não há tendências disponíveis."""
        with patch("pipeline.orchestrator.coletar_tendencias", new_callable=AsyncMock) as mock_coletar, \
             patch("pipeline.orchestrator.normalizar_tendencias", new_callable=AsyncMock) as mock_normalizar, \
             patch("pipeline.orchestrator.gerar_ideias", new_callable=AsyncMock) as mock_ideias, \
             patch("pipeline.orchestrator.salvar_ideias", new_callable=AsyncMock) as mock_salvar:

            mock_coletar.return_value = []
            mock_normalizar.return_value = []
            mock_ideias.return_value = [
                Ideia(topico=f"Tópico{i}", titulo_sugerido=f"Título {i}", descricao_breve=f"Desc {i}")
                for i in range(5)
            ]
            mock_salvar.return_value = None

            resultado = await rodar_etapa_ideacao("cultura_pop")

            # Mesmo sem tendências, deve gerar 5 ideias (evergreen)
            assert len(resultado) == 5
