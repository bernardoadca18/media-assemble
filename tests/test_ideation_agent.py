"""Testes para o agente de ideação."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from pipeline.schemas import Ideia, RespostaIdeacao
from services.ideation.agent import _parsear_resposta, gerar_ideias


class TestParseResposta:
    """Testes para o parsing de respostas do LLM."""

    def test_parsear_resposta_valida(self):
        """Testa parsing de resposta JSON válida."""
        json_valido = json.dumps({
            "ideias": [
                {"topico": "Naruto", "titulo_sugerido": "Todos os Clãs de Naruto Explicados", "descricao_breve": "Teste"},
                {"topico": "One Piece", "titulo_sugerido": "Os Piratas Mais Sombrios de One Piece", "descricao_breve": "Teste"},
                {"topico": "Bleach", "titulo_sugerido": "A História dos Soul Reapers", "descricao_breve": "Teste"},
                {"topico": "Dragon Ball", "titulo_sugerido": "As Transformações de Goku", "descricao_breve": "Teste"},
                {"topico": "Death Note", "titulo_sugerido": "Os Mistérios do Death Note", "descricao_breve": "Teste"},
            ]
        })

        resultado = _parsear_resposta(json_valido)
        assert isinstance(resultado, RespostaIdeacao)
        assert len(resultado.ideias) == 5
        assert resultado.ideias[0].topico == "Naruto"

    def test_parsear_resposta_com_markdown(self):
        """Testa parsing de resposta JSON envolta em blocos markdown."""
        json_com_markdown = """```json
{
    "ideias": [
        {"topico": "Teste1", "titulo_sugerido": "Título 1", "descricao_breve": "Desc 1"},
        {"topico": "Teste2", "titulo_sugerido": "Título 2", "descricao_breve": "Desc 2"},
        {"topico": "Teste3", "titulo_sugerido": "Título 3", "descricao_breve": "Desc 3"},
        {"topico": "Teste4", "titulo_sugerido": "Título 4", "descricao_breve": "Desc 4"},
        {"topico": "Teste5", "titulo_sugerido": "Título 5", "descricao_breve": "Desc 5"}
    ]
}
```"""

        resultado = _parsear_resposta(json_com_markdown)
        assert isinstance(resultado, RespostaIdeacao)
        assert len(resultado.ideias) == 5

    def test_parsear_resposta_menos_de_cinco_ideias(self):
        """Testa que resposta com menos de 5 ideias levanta erro."""
        json_invalido = json.dumps({
            "ideias": [
                {"topico": "Teste", "titulo_sugerido": "Título", "descricao_breve": "Desc"}
            ]
        })

        with pytest.raises(Exception):  # Pydantic ValidationError
            _parsear_resposta(json_invalido)

    def test_parsear_resposta_mais_de_cinco_ideias(self):
        """Testa que resposta com mais de 5 ideias levanta erro."""
        ideias = [{"topico": f"Teste{i}", "titulo_sugerido": f"Título {i}", "descricao_breve": f"Desc {i}"} for i in range(6)]
        json_invalido = json.dumps({"ideias": ideias})

        with pytest.raises(Exception):  # Pydantic ValidationError
            _parsear_resposta(json_invalido)

    def test_parsear_resposta_json_invalido(self):
        """Testa que JSON malformado levanta erro tratável."""
        json_invalido = "{ isso não é json válido"

        with pytest.raises(json.JSONDecodeError):
            _parsear_resposta(json_invalido)

    def test_parsear_resposta_campos_faltando(self):
        """Testa que ideias com campos faltando levanta erro."""
        json_incompleto = json.dumps({
            "ideias": [
                {"topico": "Teste"},  # faltam titulo_sugerido e descricao_breve
                {"topico": "Teste2", "titulo_sugerido": "Título", "descricao_breve": "Desc"},
                {"topico": "Teste3", "titulo_sugerido": "Título", "descricao_breve": "Desc"},
                {"topico": "Teste4", "titulo_sugerido": "Título", "descricao_breve": "Desc"},
                {"topico": "Teste5", "titulo_sugerido": "Título", "descricao_breve": "Desc"},
            ]
        })

        with pytest.raises(Exception):  # Pydantic ValidationError
            _parsear_resposta(json_incompleto)


class TestGerarIdeias:
    """Testes para a função gerar_ideias com mocks."""

    @pytest.mark.asyncio
    async def test_gerar_ideias_sucesso(self):
        """Testa geração de ideias com LLM mockado."""
        resposta_mock = json.dumps({
            "ideias": [
                {"topico": "Jujutsu Kaisen", "titulo_sugerido": "Os Feitiços Mais Poderosos de JJK", "descricao_breve": "Análise das técnicas amaldiçoadas"},
                {"topico": "Dune", "titulo_sugerido": "A História Completa de Arrakis", "descricao_breve": "Lore do universo de Duna"},
                {"topico": "Elden Ring", "titulo_sugerido": "Os Chefes Mais Brutais de Elden Ring", "descricao_breve": "Análise das batalhas épicas"},
                {"topico": "Universo Marvel", "titulo_sugerido": "Os Vilões Mais Subestimados da Marvel", "descricao_breve": "Análise de vilões esquecidos"},
                {"topico": "Harry Potter", "titulo_sugerido": "Os Mistérios Não Resolvidos de Hogwarts", "descricao_breve": "Teorias e lore obscuro"},
            ]
        })

        with patch("services.ideation.agent.buscar_titulos_recentes", new_callable=AsyncMock) as mock_titulos, \
             patch("services.ideation.agent.complete_cloud", new_callable=AsyncMock) as mock_llm:
            mock_titulos.return_value = []
            mock_llm.return_value = resposta_mock

            ideias = await gerar_ideias("cultura_pop", ["Jujutsu Kaisen", "Dune", "Elden Ring"])

            assert len(ideias) == 5
            assert ideias[0].topico == "Jujutsu Kaisen"
            mock_titulos.assert_called_once_with("cultura_pop")
            mock_llm.assert_called_once()

    @pytest.mark.asyncio
    async def test_gerar_ideias_com_historico(self):
        """Testa que histórico é passado corretamente ao prompt."""
        resposta_mock = json.dumps({
            "ideias": [
                {"topico": f"Tópico{i}", "titulo_sugerido": f"Título {i}", "descricao_breve": f"Desc {i}"}
                for i in range(1, 6)
            ]
        })

        with patch("services.ideation.agent.buscar_titulos_recentes", new_callable=AsyncMock) as mock_titulos, \
             patch("services.ideation.agent.complete_cloud", new_callable=AsyncMock) as mock_llm:
            mock_titulos.return_value = ["Vídeo Antigo 1", "Vídeo Antigo 2"]
            mock_llm.return_value = resposta_mock

            await gerar_ideias("cultura_pop", ["Tendência 1"])

            # Verifica que o prompt inclui o histórico
            call_args = mock_llm.call_args[0][0]
            assert "Vídeo Antigo 1" in call_args
            assert "Vídeo Antigo 2" in call_args

    @pytest.mark.asyncio
    async def test_gerar_ideias_llm_retorna_invalido(self):
        """Testa tratamento de erro quando LLM retorna JSON inválido."""
        with patch("services.ideation.agent.buscar_titulos_recentes", new_callable=AsyncMock) as mock_titulos, \
             patch("services.ideation.agent.complete_cloud", new_callable=AsyncMock) as mock_llm:
            mock_titulos.return_value = []
            mock_llm.return_value = "Isso não é JSON válido"

            with pytest.raises(json.JSONDecodeError):
                await gerar_ideias("cultura_pop", ["Tendência 1"])
