"""
Testes para Subfase 8.6 — Metadata de Publicação.

Valida:
- Schema MetadataPublicacao
- Geração de metadata via LLM
- Endpoint da API
- CLI command
- Integração no orchestrator
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import json

from pipeline.schemas import (
    Roteiro,
    MetadataRoteiro,
    MetadataPublicacao,
    Cena,
    Midia,
    EfeitosVisuais,
    Overlays,
    TipoAsset,
    AnimacaoImagem,
)


class TestSchemaMetadataPublicacao:
    """Testa o schema MetadataPublicacao."""

    def test_metadata_publicacao_valida(self):
        """Metadata de publicação válida."""
        metadata = MetadataPublicacao(
            titulos=["Título 1", "Título 2"],
            descricao="Descrição do vídeo com capítulos",
            tags=["tag1", "tag2", "tag3"],
            playlist_sugerida="Minha Playlist",
            playlist_nova=False,
        )
        assert len(metadata.titulos) == 2
        assert len(metadata.tags) == 3
        assert metadata.playlist_nova is False

    def test_metadata_publicacao_3_titulos(self):
        """Metadata pode ter 3 títulos."""
        metadata = MetadataPublicacao(
            titulos=["T1", "T2", "T3"],
            descricao="Desc",
            tags=["tag"],
            playlist_sugerida="Playlist",
        )
        assert len(metadata.titulos) == 3

    def test_metadata_publicacao_minimo_2_titulos(self):
        """Metadata deve ter pelo menos 2 títulos."""
        with pytest.raises(ValueError, match="at least 2"):
            MetadataPublicacao(
                titulos=["Único título"],
                descricao="Desc",
                tags=["tag"],
                playlist_sugerida="Playlist",
            )

    def test_metadata_publicacao_maximo_3_titulos(self):
        """Metadata pode ter no máximo 3 títulos."""
        with pytest.raises(ValueError, match="at most 3"):
            MetadataPublicacao(
                titulos=["T1", "T2", "T3", "T4"],
                descricao="Desc",
                tags=["tag"],
                playlist_sugerida="Playlist",
            )

    def test_metadata_publicacao_max_15_tags(self):
        """Metadata pode ter no máximo 15 tags."""
        tags = [f"tag{i}" for i in range(16)]
        with pytest.raises(ValueError, match="at most 15"):
            MetadataPublicacao(
                titulos=["T1", "T2"],
                descricao="Desc",
                tags=tags,
                playlist_sugerida="Playlist",
            )

    def test_metadata_publicacao_no_roteiro(self):
        """Roteiro pode ter metadata_publicacao opcional."""
        metadata_roteiro = MetadataRoteiro(
            video_id="test_123",
            nicho="cultura_pop",
            titulo_sugerido="Teste",
            duracao_estimada_segundos=180.0,
            trilha_fundo="epica",
        )
        assert metadata_roteiro.metadata_publicacao is None

    def test_metadata_publicacao_in_roteiro(self):
        """Roteiro pode ter metadata_publicacao preenchida."""
        metadata_pub = MetadataPublicacao(
            titulos=["T1", "T2"],
            descricao="Desc",
            tags=["tag"],
            playlist_sugerida="Playlist",
        )
        metadata_roteiro = MetadataRoteiro(
            video_id="test_123",
            nicho="cultura_pop",
            titulo_sugerido="Teste",
            duracao_estimada_segundos=180.0,
            trilha_fundo="epica",
            metadata_publicacao=metadata_pub,
        )
        assert metadata_roteiro.metadata_publicacao is not None
        assert len(metadata_roteiro.metadata_publicacao.titulos) == 2


class TestGerarMetadataPublicacao:
    """Testa geração de metadata via LLM."""

    @pytest.fixture
    def roteiro_exemplo(self) -> Roteiro:
        """Cria um roteiro de exemplo para testes."""
        metadata = MetadataRoteiro(
            video_id="test_meta_123",
            nicho="cultura_pop",
            titulo_sugerido="A História Secreta de Naruto",
            duracao_estimada_segundos=90.0,
            trilha_fundo="epica",
            video_final_path="/data/output/test_meta_123.mp4",
        )

        cenas = [
            Cena(
                cena_id=i,
                ordem=i,
                texto_locucao=f"Texto da cena {i} sobre o tema do vídeo.",
                duracao_estimada_segundos=10.0,
                midia=Midia(
                    tipo_asset_preferencial=TipoAsset.imagem,
                    keywords_busca=[f"naruto_{i}"],
                    fallback_query="naruto anime",
                    duracao_minima=10.0,
                ),
                efeitos_visuais=EfeitosVisuais(
                    animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
                ),
                overlays=Overlays(),
                asset_resolvido_path=f"assets/naruto_{i}.jpg",
            )
            for i in range(1, 10)  # 9 cenas de 10s = 90s
        ]

        return Roteiro(metadata=metadata, cenas=cenas)

    @pytest.mark.asyncio
    async def test_gerar_metadata_publicacao_sucesso(self, roteiro_exemplo):
        """Testa geração de metadata com LLM mockado."""
        from services.metadata_generator import gerar_metadata_publicacao

        mock_resposta = json.dumps({
            "titulos": [
                "O Segredo de Naruto que Você Não Conhecia",
                "10 Fatos Sobre Naruto que Vão te Surpreender",
                "Naruto: A Verdade Por Trás do Anime"
            ],
            "descricao": "Descubra os segredos mais profundos de Naruto\n\n0:00 - Introdução\n0:10 - Cena 1\n0:20 - Cena 2",
            "tags": ["naruto", "anime", "curiosidades", "mangá", "naruto shippuden"],
            "playlist_sugerida": "Curiosidades de Anime",
            "playlist_nova": False
        })

        with patch(
            "services.metadata_generator.complete_cloud",
            new_callable=AsyncMock,
            return_value=mock_resposta,
        ):
            metadata = await gerar_metadata_publicacao(roteiro_exemplo)

        assert "titulos" in metadata
        assert len(metadata["titulos"]) == 3
        assert "descricao" in metadata
        assert "tags" in metadata
        assert len(metadata["tags"]) == 5
        assert metadata["playlist_sugerida"] == "Curiosidades de Anime"

    @pytest.mark.asyncio
    async def test_gerar_metadata_publicacao_limpa_markdown(self, roteiro_exemplo):
        """Testa que função remove blocos markdown da resposta."""
        from services.metadata_generator import gerar_metadata_publicacao

        mock_resposta_com_markdown = '''```json
{
  "titulos": ["Título 1", "Título 2"],
  "descricao": "Descrição teste",
  "tags": ["tag1", "tag2"],
  "playlist_sugerida": "Minha Playlist",
  "playlist_nova": true
}
```'''

        with patch(
            "services.metadata_generator.complete_cloud",
            new_callable=AsyncMock,
            return_value=mock_resposta_com_markdown,
        ):
            metadata = await gerar_metadata_publicacao(roteiro_exemplo)

        assert metadata["titulos"] == ["Título 1", "Título 2"]
        assert metadata["playlist_nova"] is True

    @pytest.mark.asyncio
    async def test_gerar_metadata_publicacao_json_invalido(self, roteiro_exemplo):
        """Testa erro quando LLM retorna JSON inválido."""
        from services.metadata_generator import gerar_metadata_publicacao

        with patch(
            "services.metadata_generator.complete_cloud",
            new_callable=AsyncMock,
            return_value="Isso não é JSON válido",
        ):
            with pytest.raises(RuntimeError, match="JSON inválido"):
                await gerar_metadata_publicacao(roteiro_exemplo)

    @pytest.mark.asyncio
    async def test_gerar_metadata_publicacao_campo_faltando(self, roteiro_exemplo):
        """Testa erro quando LLM não retorna campo obrigatório."""
        from services.metadata_generator import gerar_metadata_publicacao

        mock_resposta_incompleta = json.dumps({
            "titulos": ["T1", "T2"],
            # Falta "descricao"
            "tags": ["tag"],
            "playlist_sugerida": "Playlist",
        })

        with patch(
            "services.metadata_generator.complete_cloud",
            new_callable=AsyncMock,
            return_value=mock_resposta_incompleta,
        ):
            with pytest.raises(RuntimeError, match="Campo obrigatório ausente"):
                await gerar_metadata_publicacao(roteiro_exemplo)

    def test_formatar_metadata_cli(self):
        """Testa formatação de metadata para CLI."""
        from services.metadata_generator import formatar_metadata_cli

        metadata = {
            "titulos": ["Título 1", "Título 2"],
            "descricao": "Descrição do vídeo\n\n0:00 - Intro",
            "tags": ["tag1", "tag2", "tag3"],
            "playlist_sugerida": "Minha Playlist",
        }

        output = formatar_metadata_cli(metadata)

        assert "TÍTULOS SUGERIDOS" in output
        assert "Título 1" in output
        assert "DESCRIÇÃO" in output
        assert "TAGS" in output
        assert "PLAYLIST SUGERIDA" in output
        assert "Minha Playlist" in output


class TestAPIMetadataEndpoint:
    """Testa endpoint da API para metadata."""

    @pytest.mark.asyncio
    async def test_endpoint_metadata_sucesso(self):
        """Testa endpoint GET /execucoes/{video_id}/metadata com sucesso."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        metadata_pub = MetadataPublicacao(
            titulos=["T1", "T2"],
            descricao="Descrição teste",
            tags=["tag"],
            playlist_sugerida="Playlist",
        )

        metadata_roteiro = MetadataRoteiro(
            video_id="test_api_123",
            nicho="cultura_pop",
            titulo_sugerido="Teste API",
            duracao_estimada_segundos=60.0,
            trilha_fundo="epica",
            video_final_path="/data/output/test.mp4",
            metadata_publicacao=metadata_pub,
        )

        roteiro_mock = Roteiro(metadata=metadata_roteiro, cenas=[])

        with patch("db.models.carregar_roteiro", new_callable=AsyncMock, return_value=roteiro_mock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/execucoes/test_api_123/metadata")

        assert response.status_code == 200
        data = response.json()
        assert data["titulos"] == ["T1", "T2"]
        assert data["playlist_sugerida"] == "Playlist"

    @pytest.mark.asyncio
    async def test_endpoint_metadata_video_nao_encontrado(self):
        """Testa endpoint com vídeo inexistente."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        with patch("db.models.carregar_roteiro", new_callable=AsyncMock, return_value=None):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/execucoes/inexistente/metadata")

        assert response.status_code == 404
        assert "não encontrado" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_endpoint_metadata_nao_gerada(self):
        """Testa endpoint quando metadata ainda não foi gerada."""
        from api.status import app
        from httpx import AsyncClient, ASGITransport

        metadata_roteiro = MetadataRoteiro(
            video_id="test_api_456",
            nicho="cultura_pop",
            titulo_sugerido="Teste",
            duracao_estimada_segundos=60.0,
            trilha_fundo="epica",
            video_final_path="/data/output/test.mp4",
            # Sem metadata_publicacao
        )

        roteiro_mock = Roteiro(metadata=metadata_roteiro, cenas=[])

        with patch("db.models.carregar_roteiro", new_callable=AsyncMock, return_value=roteiro_mock):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.get("/execucoes/test_api_456/metadata")

        assert response.status_code == 404
        assert "não gerada" in response.json()["detail"]


class TestOrquestracaoMetadata:
    """Testa integração de metadata no orquestrador."""

    @pytest.mark.asyncio
    async def test_metadata_gerada_apos_renderizacao(self):
        """Testa que metadata é gerada após renderização no pipeline."""
        from pipeline.orchestrator import rodar_pipeline_completo
        from pipeline.schemas import Ideia

        # Mock de todas as etapas do pipeline
        ideia_mock = Ideia(
            topico="Teste",
            titulo_sugerido="Título Teste",
            descricao_breve="Uma breve descrição",
            justificativa="Teste",
            potencial_viral=8.0,
        )

        metadata_roteiro = MetadataRoteiro(
            video_id="test_orch_123",
            nicho="cultura_pop",
            titulo_sugerido="Teste Orchestrator",
            duracao_estimada_segundos=60.0,
            trilha_fundo="epica",
        )

        roteiro_mock = Roteiro(
            metadata=metadata_roteiro,
            cenas=[
                Cena(
                    cena_id=1,
                    ordem=1,
                    texto_locucao="Teste",
                    duracao_estimada_segundos=60.0,
                    midia=Midia(
                        tipo_asset_preferencial=TipoAsset.imagem,
                        keywords_busca=["test"],
                        fallback_query="test",
                        duracao_minima=60.0,
                    ),
                    efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
                    overlays=Overlays(),
                )
            ]
        )

        mock_metadata = {
            "titulos": ["T1", "T2"],
            "descricao": "Descrição",
            "tags": ["tag"],
            "playlist_sugerida": "Playlist",
            "playlist_nova": False,
        }

        with patch("pipeline.orchestrator.rodar_etapa_ideacao", new_callable=AsyncMock, return_value=[ideia_mock]):
            with patch("pipeline.orchestrator.rodar_etapa_roteirizacao", new_callable=AsyncMock, return_value=roteiro_mock):
                with patch("services.audio.pipeline_audio.gerar_audio_do_roteiro", new_callable=AsyncMock, return_value=roteiro_mock):
                    with patch("services.visual.asset_resolver.resolver_assets_do_roteiro", new_callable=AsyncMock, return_value=roteiro_mock):
                        with patch("services.render.remotion_bridge.renderizar_video", new_callable=AsyncMock, return_value=MagicMock()):
                            with patch("services.metadata_generator.gerar_metadata_publicacao", new_callable=AsyncMock, return_value=mock_metadata):
                                with patch("pipeline.orchestrator.salvar_roteiro", new_callable=AsyncMock):
                                    with patch("pipeline.orchestrator.salvar_execucao", new_callable=AsyncMock):
                                        with patch("pipeline.orchestrator._should_generate_shorts", return_value=False):
                                            resultado = await rodar_pipeline_completo("cultura_pop")

        assert resultado["sucesso"] is True


class TestBackwardCompatibility:
    """Testa compatibilidade com roteiros antigos."""

    def test_roteiro_antigo_sem_metadata_publicacao_serializa(self):
        """Roteiro antigo sem campo metadata_publicacao deve serializar."""
        roteiro_json = {
            "metadata": {
                "video_id": "antigo_123",
                "nicho": "cultura_pop",
                "titulo_sugerido": "Vídeo Antigo",
                "duracao_estimada_segundos": 180.0,
                "trilha_fundo": "epica",
                "volume_trilha_fundo": 0.15,
                "audio_final_path": None,
                "palavras_transcritas": None,
                "video_final_path": None,
                "formato": "longo",
                # Sem campo metadata_publicacao
            },
            "cenas": [],
        }

        roteiro = Roteiro.model_validate(roteiro_json)
        assert roteiro.metadata.metadata_publicacao is None
