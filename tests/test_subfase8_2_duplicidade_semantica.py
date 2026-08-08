"""
Testes da Subfase 8.2 — Duplicidade semântica real.

Cobertura:
- Geração de embeddings via LiteLLM
- Checagem de similaridade via pgvector
- Integração com salvar_ideias
- Configuração de limiar
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import os


# ============================================================================
# Testes de generate_embedding
# ============================================================================

@pytest.mark.asyncio
async def test_generate_embedding_sucesso():
    """generate_embedding deve retornar lista de floats."""
    from utils.litellm_client import generate_embedding

    # Mock do litellm.aembedding
    mock_response = MagicMock()
    mock_response.data = [{"embedding": [0.1, 0.2, 0.3, 0.4]}]
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 10

    with patch("utils.litellm_client.litellm.aembedding", new_callable=AsyncMock) as mock_aemb:
        mock_aemb.return_value = mock_response

        embedding = await generate_embedding(
            text="Título de teste",
            model="text-embedding-3-small",
        )

        assert isinstance(embedding, list)
        assert len(embedding) == 4
        assert embedding == [0.1, 0.2, 0.3, 0.4]
        mock_aemb.assert_called_once()


@pytest.mark.asyncio
async def test_generate_embedding_com_proxy_litellm():
    """generate_embedding deve usar proxy LiteLLM se configurado."""
    from utils.litellm_client import generate_embedding
    from pipeline.config import settings

    mock_response = MagicMock()
    mock_response.data = [{"embedding": [0.5, 0.6]}]
    mock_usage = MagicMock()
    mock_usage.prompt_tokens = 5
    mock_response.usage = mock_usage

    with patch("utils.litellm_client.litellm.aembedding", new_callable=AsyncMock) as mock_aemb:
        mock_aemb.return_value = mock_response
        with patch.object(settings, "litellm_base_url", "http://litellm-proxy:4000"):
            with patch.object(settings, "litellm_master_key", "sk-test-key"):
                embedding = await generate_embedding(text="Test")

                # Verificar que api_base e api_key foram passados
                call_kwargs = mock_aemb.call_args[1]
                assert call_kwargs["api_base"] == "http://litellm-proxy:4000"
                assert call_kwargs["api_key"] == "sk-test-key"


@pytest.mark.asyncio
async def test_generate_embedding_erro():
    """generate_embedding deve propagar erros."""
    from utils.litellm_client import generate_embedding

    with patch("utils.litellm_client.litellm.aembedding", new_callable=AsyncMock) as mock_aemb:
        mock_aemb.side_effect = Exception("API Error")

        with pytest.raises(Exception, match="API Error"):
            await generate_embedding(text="Test")


# ============================================================================
# Testes de checar_duplicidade_semantica
# ============================================================================

@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_encontra_duplicata():
    """Deve retornar True quando similaridade >= limiar."""
    from services.ideation.rag_client import checar_duplicidade_semantica

    # Mock do embedding
    mock_embedding = [0.1] * 1536

    # Mock do banco retornando título similar
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        ("Título Existente Similar", 0.92)  # similaridade acima do limiar
    ]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_gen_emb.return_value = mock_embedding

        with patch("services.ideation.rag_client.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            resultado = await checar_duplicidade_semantica(
                titulo_candidato="Título Muito Similar",
                nicho="tecnologia",
                limiar=0.85,
            )

            assert resultado is True


@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_sem_duplicata():
    """Deve retornar False quando similaridade < limiar."""
    from services.ideation.rag_client import checar_duplicidade_semantica

    mock_embedding = [0.1] * 1536

    # Mock do banco retornando títulos com baixa similaridade
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        ("Título Diferente 1", 0.45),
        ("Título Diferente 2", 0.52),
    ]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_gen_emb.return_value = mock_embedding

        with patch("services.ideation.rag_client.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            resultado = await checar_duplicidade_semantica(
                titulo_candidato="Título Único",
                nicho="cultura_pop",
                limiar=0.85,
            )

            assert resultado is False


@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_nenhum_embedding_no_nicho():
    """Deve retornar False quando não há embeddings no nicho."""
    from services.ideation.rag_client import checar_duplicidade_semantica

    mock_embedding = [0.1] * 1536

    # Mock do banco retornando lista vazia
    mock_result = MagicMock()
    mock_result.fetchall.return_value = []

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_gen_emb.return_value = mock_embedding

        with patch("services.ideation.rag_client.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            resultado = await checar_duplicidade_semantica(
                titulo_candidato="Primeiro Vídeo",
                nicho="nicho_novo",
            )

            assert resultado is False


@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_erro_embedding():
    """Deve retornar False em caso de erro (não bloqueia ideação)."""
    from services.ideation.rag_client import checar_duplicidade_semantica

    with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_gen_emb.side_effect = Exception("Erro ao gerar embedding")

        resultado = await checar_duplicidade_semantica(
            titulo_candidato="Título",
            nicho="tecnologia",
        )

        assert resultado is False


@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_limiar_customizado():
    """Deve usar limiar passado como parâmetro."""
    from services.ideation.rag_client import checar_duplicidade_semantica

    mock_embedding = [0.1] * 1536

    # Similaridade de 0.80
    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        ("Título Existente", 0.80),
    ]

    mock_session = AsyncMock()
    mock_session.execute.return_value = mock_result

    with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_gen_emb.return_value = mock_embedding

        with patch("services.ideation.rag_client.AsyncSessionLocal") as mock_session_factory:
            mock_session_factory.return_value.__aenter__.return_value = mock_session

            # Com limiar 0.85, não é duplicata
            resultado = await checar_duplicidade_semantica(
                titulo_candidato="Título",
                nicho="tecnologia",
                limiar=0.85,
            )
            assert resultado is False

            # Com limiar 0.75, é duplicata
            resultado = await checar_duplicidade_semantica(
                titulo_candidato="Título",
                nicho="tecnologia",
                limiar=0.75,
            )
            assert resultado is True


@pytest.mark.asyncio
async def test_checar_duplicidade_semantica_limiar_env_var():
    """Deve usar LIMIAR_DUPLICIDADE_SEMANTICA do ambiente se não passado."""
    # Primeiro, definir a variável de ambiente
    with patch.dict(os.environ, {"LIMIAR_DUPLICIDADE_SEMANTICA": "0.80"}):
        # Recarregar o módulo para pegar novo valor
        import importlib
        import services.ideation.rag_client as rag_mod
        importlib.reload(rag_mod)

        from services.ideation.rag_client import checar_duplicidade_semantica as checar_reload

        mock_embedding = [0.1] * 1536

        # Similaridade de 0.83
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            ("Título Existente", 0.83),
        ]

        mock_session = AsyncMock()
        mock_session.execute.return_value = mock_result

        with patch("services.ideation.rag_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
            mock_gen_emb.return_value = mock_embedding

            with patch("services.ideation.rag_client.AsyncSessionLocal") as mock_session_factory:
                mock_session_factory.return_value.__aenter__.return_value = mock_session

                resultado = await checar_reload(
                    titulo_candidato="Título",
                    nicho="tecnologia",
                )

                # 0.83 >= 0.80, então é duplicata
                assert resultado is True


# ============================================================================
# Testes de integração com salvar_ideias
# ============================================================================

@pytest.mark.asyncio
async def test_salvar_ideias_com_embedding():
    """salvar_ideias deve gerar e salvar embedding quando gerar_embedding=True."""
    from db.models import salvar_ideias

    # Criar mock de Ideia
    mock_ideia = MagicMock()
    mock_ideia.topico = "Tendência teste"
    mock_ideia.titulo_sugerido = "Título do vídeo"
    mock_ideia.descricao_breve = "Descrição"
    mock_ideia.nicho = "tecnologia"

    mock_embedding = [0.1, 0.2, 0.3]

    mock_session = AsyncMock()

    with patch("db.models.AsyncSessionLocal") as mock_session_factory, \
         patch("utils.litellm_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_gen_emb.return_value = mock_embedding

        await salvar_ideias([mock_ideia], gerar_embedding=True)

        # Verificar que registro foi adicionado com embedding
        registro = mock_session.add.call_args[0][0]
        assert registro.embedding is not None
        assert "0.1" in registro.embedding


@pytest.mark.asyncio
async def test_salvar_ideias_sem_embedding():
    """salvar_ideias não deve gerar embedding quando gerar_embedding=False."""
    from db.models import salvar_ideias

    mock_ideia = MagicMock()
    mock_ideia.topico = "Tendência"
    mock_ideia.titulo_sugerido = "Título"
    mock_ideia.descricao_breve = "Desc"
    mock_ideia.nicho = "futebol"

    mock_session = AsyncMock()

    with patch("db.models.AsyncSessionLocal") as mock_session_factory:
        mock_session_factory.return_value.__aenter__.return_value = mock_session

        await salvar_ideias([mock_ideia], gerar_embedding=False)

        # Verificar que registro foi adicionado sem embedding
        registro = mock_session.add.call_args[0][0]
        assert registro.embedding is None


@pytest.mark.asyncio
async def test_salvar_ideias_erro_embedding_nao_bloqueia():
    """Erro ao gerar embedding não deve bloquear salvamento da ideia."""
    from db.models import salvar_ideias

    mock_ideia = MagicMock()
    mock_ideia.topico = "Teste"
    mock_ideia.titulo_sugerido = "Título"
    mock_ideia.descricao_breve = "Desc"
    mock_ideia.nicho = "cultura_pop"

    mock_session = AsyncMock()

    with patch("db.models.AsyncSessionLocal") as mock_session_factory, \
         patch("utils.litellm_client.generate_embedding", new_callable=AsyncMock) as mock_gen_emb:
        mock_session_factory.return_value.__aenter__.return_value = mock_session
        mock_gen_emb.side_effect = Exception("Erro no embedding")

        await salvar_ideias([mock_ideia], gerar_embedding=True)

        # Registro deve ser salvo mesmo com erro no embedding
        mock_session.add.assert_called_once()
        registro = mock_session.add.call_args[0][0]
        assert registro.embedding is None  # Não foi possível gerar
