"""
Testes para Subfase 8.9.2 — Expansão de fallback de imagem.

Valida:
- Busca em novas fontes: Pixabay, Unsplash, Wikimedia Commons
- Campos de licenciamento/atribuição no AssetExterno
- Triagem por LLM antes de aceitar asset
- Cascata de fallback (Pexels → Pixabay → Unsplash → Wikimedia)
- Tratamento de erros transitórios/permanentes
"""
import os
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from services.visual.fallback_scraper import (
    AssetExterno,
    _buscar_pixabay,
    _buscar_unsplash,
    _buscar_wikimedia,
    buscar_asset_externo,
    _baixar_asset_interno,
)
from services.visual.triagem_llm import triar_asset_llm


class TestAssetExternoCampos:
    """Testa campos de licenciamento no AssetExterno."""

    def test_asset_externo_campos_padrao(self):
        """Asset com campos de licenciamento opcionais."""
        asset = AssetExterno(
            path=Path("/tmp/test.jpg"),
            origem="fallback_pexels",
        )
        assert asset.atribuicao_requerida is False
        assert asset.texto_atribuicao is None
        assert asset.licenca is None
        assert asset.fotografo is None
        assert asset.url_perfil is None

    def test_asset_externo_com_atribuicao(self):
        """Asset com atribuição obrigatória."""
        asset = AssetExterno(
            path=Path("/tmp/test.jpg"),
            origem="fallback_unsplash",
            atribuicao_requerida=True,
            texto_atribuicao="Photo by John Doe on Unsplash",
            licenca="Unsplash License",
            fotografo="John Doe",
            url_perfil="https://unsplash.com/@johndoe",
        )
        assert asset.atribuicao_requerida is True
        assert "John Doe" in asset.texto_atribuicao
        assert asset.licenca == "Unsplash License"


class TestBuscarPixabay:
    """Testa busca no Pixabay."""

    @pytest.mark.asyncio
    async def test_pixabay_sem_api_key(self):
        """Retorna None se API key não configurada."""
        with patch.dict(os.environ, {}, clear=True):
            resultado = await _buscar_pixabay("test query", "imagem")
        assert resultado is None

    @pytest.mark.asyncio
    async def test_pixabay_imagem_sucesso(self):
        """Busca imagem no Pixabay com sucesso."""
        mock_response = {
            "hits": [
                {
                    "id": 12345,
                    "user": "photographer",
                    "user_id": 999,
                    "largeImageURL": "https://example.com/image.jpg",
                }
            ]
        }

        with patch.dict(os.environ, {"PIXABAY_API_KEY": "test_key"}):
            with patch("services.visual.fallback_scraper.com_retry") as mock_retry:
                mock_retry.return_value = mock_response

                with patch("services.visual.fallback_scraper._baixar_asset_interno") as mock_baixar:
                    mock_baixar.return_value = AssetExterno(
                        path=Path("/tmp/test.jpg"),
                        origem="fallback_pixabay",
                        atribuicao_requerida=False,
                        licenca="Pixabay License",
                    )

                    resultado = await _buscar_pixabay("test query", "imagem")

        assert resultado is not None
        assert resultado.origem == "fallback_pixabay"
        assert resultado.atribuicao_requerida is False
        assert resultado.licenca == "Pixabay License"

    @pytest.mark.asyncio
    async def test_pixabay_sem_resultados(self):
        """Retorna None se não houver resultados."""
        mock_response = {"hits": []}

        with patch.dict(os.environ, {"PIXABAY_API_KEY": "test_key"}):
            with patch("services.visual.fallback_scraper.com_retry") as mock_retry:
                mock_retry.return_value = mock_response

                resultado = await _buscar_pixabay("test query", "imagem")

        assert resultado is None


class TestBuscarUnsplash:
    """Testa busca no Unsplash."""

    @pytest.mark.asyncio
    async def test_unsplash_sem_api_key(self):
        """Retorna None se API key não configurada."""
        with patch.dict(os.environ, {}, clear=True):
            resultado = await _buscar_unsplash("test query", "imagem")
        assert resultado is None

    @pytest.mark.asyncio
    async def test_unsplash_atribuicao_obrigatoria(self):
        """Verifica que atribuição é marcada como obrigatória."""
        mock_response = {
            "results": [
                {
                    "id": "abc123",
                    "urls": {
                        "regular": "https://example.com/photo.jpg"
                    },
                    "user": {
                        "name": "John Doe",
                        "username": "johndoe"
                    }
                }
            ]
        }

        with patch.dict(os.environ, {"UNSPLASH_ACCESS_KEY": "test_key"}):
            with patch("services.visual.fallback_scraper.com_retry") as mock_retry:
                mock_retry.return_value = mock_response

                with patch("services.visual.fallback_scraper._baixar_asset_interno") as mock_baixar:
                    mock_baixar.return_value = AssetExterno(
                        path=Path("/tmp/test.jpg"),
                        origem="fallback_unsplash",
                        atribuicao_requerida=True,
                        texto_atribuicao="Photo by John Doe on Unsplash",
                        licenca="Unsplash License",
                        fotografo="John Doe",
                    )

                    resultado = await _buscar_unsplash("test query", "imagem")

        assert resultado is not None
        assert resultado.atribuicao_requerida is True
        assert "John Doe" in resultado.texto_atribuicao
        assert resultado.licenca == "Unsplash License"


class TestBuscarWikimedia:
    """Testa busca no Wikimedia Commons."""

    @pytest.mark.asyncio
    async def test_wikimedia_licenca_variavel(self):
        """Lê licença específica de cada arquivo."""
        mock_response = {
            "query": {
                "pages": {
                    "123": {
                        "title": "File:Test.jpg",
                        "pageid": 123,
                        "imageinfo": [
                            {
                                "url": "https://example.com/file.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "CC BY-SA 4.0"},
                                    "AttributionRequired": {"value": "true"},
                                    "Artist": {"value": "John Doe"}
                                }
                            }
                        ]
                    }
                }
            }
        }

        with patch("services.visual.fallback_scraper.com_retry") as mock_retry:
            mock_retry.return_value = mock_response

            with patch("services.visual.fallback_scraper._baixar_asset_interno") as mock_baixar:
                mock_baixar.return_value = AssetExterno(
                    path=Path("/tmp/test.jpg"),
                    origem="fallback_wikimedia",
                    atribuicao_requerida=True,
                    texto_atribuicao="John Doe - Wikimedia Commons (CC BY-SA 4.0)",
                    licenca="CC BY-SA 4.0",
                    fotografo="John Doe",
                )

                resultado = await _buscar_wikimedia("test query", "imagem")

        assert resultado is not None
        assert resultado.licenca == "CC BY-SA 4.0"
        assert resultado.atribuicao_requerida is True

    @pytest.mark.asyncio
    async def test_wikimedia_dominio_publico(self):
        """Arquivo em domínio público não exige atribuição."""
        mock_response = {
            "query": {
                "pages": {
                    "456": {
                        "title": "File:Public.jpg",
                        "pageid": 456,
                        "imageinfo": [
                            {
                                "url": "https://example.com/public.jpg",
                                "extmetadata": {
                                    "LicenseShortName": {"value": "Public domain"},
                                    "AttributionRequired": {"value": "false"},
                                    "Artist": {"value": "Unknown"}
                                }
                            }
                        ]
                    }
                }
            }
        }

        with patch("services.visual.fallback_scraper.com_retry") as mock_retry:
            mock_retry.return_value = mock_response

            with patch("services.visual.fallback_scraper._baixar_asset_interno") as mock_baixar:
                mock_baixar.return_value = AssetExterno(
                    path=Path("/tmp/test.jpg"),
                    origem="fallback_wikimedia",
                    atribuicao_requerida=False,
                    licenca="Public domain",
                )

                resultado = await _buscar_wikimedia("test query", "imagem")

        assert resultado is not None
        assert resultado.atribuicao_requerida is False
        assert resultado.licenca == "Public domain"


class TestTriagemLLM:
    """Testa triagem de assets por LLM."""

    @pytest.mark.asyncio
    async def test_triagem_aprovado(self):
        """LLM aprova asset."""
        with patch("services.visual.triagem_llm.complete_cloud") as mock_llm:
            mock_llm.return_value = '{"aprovado": true, "motivo": "Asset relevante para a cena"}'

            resultado = await triar_asset_llm(
                descricao_asset="Paisagem tropical",
                contexto_cena="Cena sobre natureza",
                keywords=["natureza", "tropical"],
            )

        assert resultado is True

    @pytest.mark.asyncio
    async def test_triagem_reprovado(self):
        """LLM reprova asset."""
        with patch("services.visual.triagem_llm.complete_cloud") as mock_llm:
            mock_llm.return_value = '{"aprovado": false, "motivo": "Asset não relacionado ao tema"}'

            resultado = await triar_asset_llm(
                descricao_asset="Cidade urbana",
                contexto_cena="Cena sobre floresta tropical",
                keywords=["natureza", "floresta"],
            )

        assert resultado is False

    @pytest.mark.asyncio
    async def test_triagem_erro_json(self):
        """Erro de parsing JSON assume aprovado (não bloqueia)."""
        with patch("services.visual.triagem_llm.complete_cloud") as mock_llm:
            mock_llm.return_value = "isso não é JSON válido"

            resultado = await triar_asset_llm(
                descricao_asset="Teste",
                contexto_cena="Contexto",
                keywords=["test"],
            )

        # Não deve bloquear pipeline
        assert resultado is True


class TestCascataFallback:
    """Testa cascata de fallback entre fontes."""

    @pytest.mark.asyncio
    async def test_cascata_pexels_sucesso(self):
        """Para na primeira fonte (Pexels) se encontrar."""
        with patch("services.visual.fallback_scraper._buscar_pexels") as mock_pexels:
            mock_pexels.return_value = AssetExterno(
                path=Path("/tmp/pexels.jpg"),
                origem="fallback_pexels",
            )

            resultado = await buscar_asset_externo(
                keywords=["test"],
                fallback_query="test query",
                tipo_asset="imagem",
                usar_triagem_llm=False,  # Desabilita triagem para simplificar
            )

        assert resultado is not None
        assert resultado.origem == "fallback_pexels"
        mock_pexels.assert_called_once()

    @pytest.mark.asyncio
    async def test_cascata_pulas_pixabay_unsplash(self):
        """Pula para próximas fontes se anteriores falharem."""
        with patch("services.visual.fallback_scraper._buscar_pexels", return_value=None) as mock_pexels:
            with patch("services.visual.fallback_scraper._buscar_pixabay", return_value=None) as mock_pixabay:
                with patch("services.visual.fallback_scraper._buscar_unsplash") as mock_unsplash:
                    mock_unsplash.return_value = AssetExterno(
                        path=Path("/tmp/unsplash.jpg"),
                        origem="fallback_unsplash",
                        atribuicao_requerida=True,
                    )

                    resultado = await buscar_asset_externo(
                        keywords=["test"],
                        fallback_query="test query",
                        tipo_asset="imagem",
                        usar_triagem_llm=False,
                    )

        assert resultado is not None
        assert resultado.origem == "fallback_unsplash"
        assert resultado.atribuicao_requerida is True
        mock_pexels.assert_called_once()
        mock_pixabay.assert_called_once()
        mock_unsplash.assert_called_once()

    @pytest.mark.asyncio
    async def test_cascata_todas_falham(self):
        """Retorna None se todas as fontes falharem."""
        with patch("services.visual.fallback_scraper._buscar_pexels", return_value=None):
            with patch("services.visual.fallback_scraper._buscar_pixabay", return_value=None):
                with patch("services.visual.fallback_scraper._buscar_unsplash", return_value=None):
                    with patch("services.visual.fallback_scraper._buscar_wikimedia", return_value=None):
                        resultado = await buscar_asset_externo(
                            keywords=["test"],
                            fallback_query="test query",
                            tipo_asset="imagem",
                            usar_triagem_llm=False,
                        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_triagem_rejeita_pula_proxima_fonte(self):
        """Se triagem reprova, tenta próxima fonte."""
        asset_pexels = AssetExterno(
            path=Path("/tmp/pexels.jpg"),
            origem="fallback_pexels",
        )

        asset_pixabay = AssetExterno(
            path=Path("/tmp/pixabay.jpg"),
            origem="fallback_pixabay",
        )

        with patch("services.visual.fallback_scraper._buscar_pexels", return_value=asset_pexels):
            with patch("services.visual.fallback_scraper._buscar_pixabay", return_value=asset_pixabay):
                with patch("services.visual.triagem_llm.triar_asset_llm") as mock_triagem:
                    # Primeiro rejeita, segundo aprova
                    mock_triagem.side_effect = [False, True]

                    resultado = await buscar_asset_externo(
                        keywords=["test"],
                        fallback_query="test query",
                        tipo_asset="imagem",
                        contexto_cena="Contexto da cena",
                        usar_triagem_llm=True,
                    )

        assert resultado is not None
        assert resultado.origem == "fallback_pixabay"
        assert mock_triagem.call_count == 2


class TestBaixarAssetInterno:
    """Testa download de assets com campos de licença."""

    @pytest.mark.asyncio
    async def test_baixar_com_atribuicao(self):
        """Baixa asset e registra atribuição."""
        mock_response = MagicMock()
        mock_response.content = b"fake_image_data"
        mock_response.raise_for_status = MagicMock()
        mock_response.headers = {"content-type": "image/jpeg"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client_instance = AsyncMock()
            mock_client_instance.get = AsyncMock(return_value=mock_response)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock(return_value=None)
            mock_client.return_value = mock_client_instance

            resultado = await _baixar_asset_interno(
                url="https://example.com/photo.jpg",
                nome_base="test_photo",
                tipo_asset="imagem",
                origem="fallback_unsplash",
                atribuicao_requerida=True,
                texto_atribuicao="Photo by John Doe",
                licenca="Unsplash License",
                fotografo="John Doe",
            )

        assert resultado.atribuicao_requerida is True
        assert resultado.texto_atribuicao == "Photo by John Doe"
        assert resultado.licenca == "Unsplash License"
        assert resultado.fotografo == "John Doe"
