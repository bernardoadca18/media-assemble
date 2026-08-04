"""
Testes para a Fase 4 — Resolução de assets visuais.

Cobre:
- Indexação do banco local
- Casamento de keywords contra tags
- Fallback via Pexels (mockado)
- Cena sem asset resolvido
"""
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from pipeline.schemas import (
    Cena,
    Midia,
    EfeitosVisuais,
    Overlays,
    MetadataRoteiro,
    Roteiro,
    TipoAsset,
    AnimacaoImagem,
)
from services.visual.asset_resolver import (
    _normalizar_tag,
    _construir_indice_local,
    _buscar_no_banco_local,
    _recarregar_indice,
    resolver_asset_cena,
    resolver_assets_do_roteiro,
    BANCO_LOCAL_DIR,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def banco_local_temporario(tmp_path: Path):
    """
    Cria um banco local temporário com estrutura de tags para testes.
    """
    # Cria estrutura de diretórios
    doctor_doom = tmp_path / "doctor_doom"
    doctor_doom.mkdir()
    (doctor_doom / "img1.jpg").touch()
    (doctor_doom / "img2.png").touch()

    naruto = tmp_path / "naruto"
    naruto.mkdir()
    (naruto / "clip1.mp4").touch()

    # Tag com nome composto (testa normalização)
    marvel_comics = tmp_path / "Marvel Comics"
    marvel_comics.mkdir()
    (marvel_comics / "hero1.jpg").touch()

    # Ignora diretórios especiais
    ignored = tmp_path / "_fallback_cache"
    ignored.mkdir()
    (ignored / "cached.jpg").touch()

    hidden = tmp_path / ".hidden"
    hidden.mkdir()
    (hidden / "secret.jpg").touch()

    return tmp_path


@pytest.fixture
def cena_exemplo() -> Cena:
    """Cria uma cena de exemplo para testes."""
    return Cena(
        cena_id=1,
        ordem=1,
        texto_locucao="Doctor Doom é um dos maiores vilões da Marvel.",
        duracao_estimada_segundos=5.0,
        midia=Midia(
            tipo_asset_preferencial=TipoAsset.imagem,
            keywords_busca=["Doctor Doom", "vilão Marvel"],
            fallback_query="doctor doom marvel villain",
            duracao_minima=3.0,
        ),
        efeitos_visuais=EfeitosVisuais(
            animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
        ),
        overlays=Overlays(
            exibir_legenda=True,
        ),
    )


@pytest.fixture
def roteiro_exemplo(cena_exemplo: Cena) -> Roteiro:
    """Cria um roteiro de exemplo para testes."""
    metadata = MetadataRoteiro(
        video_id="test_video_123",
        nicho="cultura_pop",
        titulo_sugerido="Top 10 Vilões da Marvel",
        duracao_estimada_segundos=60.0,
        trilha_fundo="epic_music.mp3",
    )

    cena2 = Cena(
        cena_id=2,
        ordem=2,
        texto_locucao="Naruto é um ninja determinado.",
        duracao_estimada_segundos=4.0,
        midia=Midia(
            tipo_asset_preferencial=TipoAsset.video,
            keywords_busca=["Naruto anime"],
            fallback_query="naruto anime",
            duracao_minima=3.0,
        ),
        efeitos_visuais=EfeitosVisuais(
            animacao_imagem=AnimacaoImagem.pan_lateral,
        ),
        overlays=Overlays(
            exibir_legenda=True,
        ),
    )

    cena3 = Cena(
        cena_id=3,
        ordem=3,
        texto_locucao="Um herói sem assets.",
        duracao_estimada_segundos=3.0,
        midia=Midia(
            tipo_asset_preferencial=TipoAsset.imagem,
            keywords_busca=["herói desconhecido xyz"],
            fallback_query="unknown hero",
            duracao_minima=2.0,
        ),
        efeitos_visuais=EfeitosVisuais(
            animacao_imagem=AnimacaoImagem.ken_burns_zoom_out,
        ),
        overlays=Overlays(
            exibir_legenda=True,
        ),
    )

    return Roteiro(metadata=metadata, cenas=[cena_exemplo, cena2, cena3])


# ---------------------------------------------------------------------------
# Testes de normalização de tags
# ---------------------------------------------------------------------------

class TestNormalizarTag:
    """Testes para a função _normalizar_tag."""

    def test_minusculas(self):
        assert _normalizar_tag("DOCTOR DOOM") == "doctor_doom"

    def test_remove_acentos(self):
        assert _normalizar_tag("vilão") == "vilao"
        assert _normalizar_tag("herói") == "heroi"

    def test_espacos_viram_underscores(self):
        assert _normalizar_tag("doctor doom") == "doctor_doom"

    def test_hifens_viram_underscores(self):
        assert _normalizar_tag("spider-man") == "spider_man"

    def test_caracteres_especiais_removidos(self):
        assert _normalizar_tag("doctor@doom!") == "doctordoom"

    def test_underscores_duplicados_removidos(self):
        assert _normalizar_tag("doctor  doom") == "doctor_doom"

    def test_underscores_inicio_fim_removidos(self):
        assert _normalizar_tag("_doctor_doom_") == "doctor_doom"

    def test_string_vazia(self):
        assert _normalizar_tag("") == ""
        assert _normalizar_tag("   ") == ""


# ---------------------------------------------------------------------------
# Testes de indexação do banco local
# ---------------------------------------------------------------------------

class TestConstruirIndiceLocal:
    """Testes para a indexação do banco local."""

    def test_indice_vazio_se_diretorio_nao_existe(self, monkeypatch):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            Path("/caminho/inexistente/xyz"),
        )
        _recarregar_indice()
        indice = _construir_indice_local()
        assert indice == {}

    def test_indice_construido_corretamente(
        self, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        indice = _construir_indice_local()

        # Verifica tags criadas
        assert "doctor_doom" in indice
        assert "naruto" in indice
        assert "marvel_comics" in indice

        # Verifica quantidade de arquivos
        assert len(indice["doctor_doom"]) == 2
        assert len(indice["naruto"]) == 1
        assert len(indice["marvel_comics"]) == 1

        # Verifica que diretórios especiais são ignorados
        assert "_fallback_cache" not in indice
        assert "hidden" not in indice

    def test_ignora_arquivos_soltos(self, banco_local_temporario: Path, monkeypatch):
        # Adiciona um arquivo solto no diretório raiz
        arquivo_solto = banco_local_temporario / "arquivo_solto.jpg"
        arquivo_solto.touch()

        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        indice = _construir_indice_local()

        # Não deve criar uma tag para o arquivo solto
        assert "arquivo_solto" not in indice


# ---------------------------------------------------------------------------
# Testes de casamento de keywords
# ---------------------------------------------------------------------------

class TestBuscarNoBancoLocal:
    """Testes para a busca de assets no banco local."""

    def test_match_exato(self, banco_local_temporario: Path, monkeypatch):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        resultado = _buscar_no_banco_local(["doctor_doom"])

        assert resultado is not None
        assert resultado.origem == "banco_local"
        assert "doctor_doom" in str(resultado.path)

    def test_match_parcial_keyword_contem_tag(
        self, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # "doctor_doom_art" contém "doctor_doom"
        resultado = _buscar_no_banco_local(["doctor_doom_art"])

        assert resultado is not None
        assert resultado.origem == "banco_local"

    def test_match_parcial_tag_contem_keyword(
        self, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # "doom" está contido em "doctor_doom"
        resultado = _buscar_no_banco_local(["doom"])

        assert resultado is not None
        assert resultado.origem == "banco_local"

    def test_match_com_acentos_normalizados(
        self, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # "vilão" normaliza para "vilao"
        resultado = _buscar_no_banco_local(["vilão"])

        # Não há tag "vilao", então deve retornar None
        assert resultado is None

    def test_sem_match(self, banco_local_temporario: Path, monkeypatch):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        resultado = _buscar_no_banco_local(["spiderman_xyz_inexistente"])

        assert resultado is None

    def test_keywords_vazias(self, banco_local_temporario: Path, monkeypatch):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        resultado = _buscar_no_banco_local([])

        assert resultado is None


# ---------------------------------------------------------------------------
# Testes de resolução de asset por cena
# ---------------------------------------------------------------------------

class TestResolverAssetCena:
    """Testes para resolver_asset_cena."""

    @pytest.mark.asyncio
    async def test_resolvido_banco_local(
        self, cena_exemplo: Cena, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        resultado = await resolver_asset_cena(cena_exemplo)

        assert resultado is True
        assert cena_exemplo.asset_resolvido_path is not None
        assert cena_exemplo.asset_origem == "banco_local"
        assert cena_exemplo.revisao_manual_necessaria is False

    @pytest.mark.asyncio
    async def test_fallback_acionado(
        self, cena_exemplo: Cena, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # Modifica keywords para não encontrar no banco local
        cena_exemplo.midia.keywords_busca = ["keyword_inexistente_xyz"]

        # Mocka o fallback para retornar um asset
        with patch(
            "services.visual.asset_resolver.buscar_asset_externo",
            new_callable=AsyncMock,
        ) as mock_fallback:
            mock_fallback.return_value = MagicMock(
                path=Path("/tmp/fallback_asset.jpg"),
                origem="fallback_pexels",
            )

            resultado = await resolver_asset_cena(cena_exemplo)

            assert resultado is True
            assert cena_exemplo.asset_resolvido_path is not None
            assert cena_exemplo.asset_origem == "fallback_pexels"
            assert mock_fallback.called

    @pytest.mark.asyncio
    async def test_sem_asset_encontrado(
        self, cena_exemplo: Cena, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # Modifica keywords para não encontrar no banco local
        cena_exemplo.midia.keywords_busca = ["keyword_inexistente_xyz"]

        # Mocka o fallback para retornar None (sem asset)
        with patch(
            "services.visual.asset_resolver.buscar_asset_externo",
            new_callable=AsyncMock,
        ) as mock_fallback:
            mock_fallback.return_value = None

            resultado = await resolver_asset_cena(cena_exemplo)

            assert resultado is False
            assert cena_exemplo.asset_resolvido_path is None
            assert cena_exemplo.revisao_manual_necessaria is True


# ---------------------------------------------------------------------------
# Testes de resolução de roteiro completo
# ---------------------------------------------------------------------------

class TestResolverAssetsDoRoteiro:
    """Testes para resolver_assets_do_roteiro."""

    @pytest.mark.asyncio
    async def test_roteiro_com_assets_mistos(
        self, roteiro_exemplo: Roteiro, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        # Mocka o fallback para retornar None (simula Pexels sem resultados)
        with patch(
            "services.visual.asset_resolver.buscar_asset_externo",
            new_callable=AsyncMock,
        ) as mock_fallback:
            mock_fallback.return_value = None

            roteiro = await resolver_assets_do_roteiro(roteiro_exemplo)

            # Cena 1: Doctor Doom - deve encontrar no banco local
            assert roteiro.cenas[0].asset_resolvido_path is not None
            assert roteiro.cenas[0].asset_origem == "banco_local"

            # Cena 2: Naruto - deve encontrar no banco local
            assert roteiro.cenas[1].asset_resolvido_path is not None
            assert roteiro.cenas[1].asset_origem == "banco_local"

            # Cena 3: herói desconhecido - não deve encontrar, marcada para revisão
            assert roteiro.cenas[2].asset_resolvido_path is None
            assert roteiro.cenas[2].revisao_manual_necessaria is True

    @pytest.mark.asyncio
    async def test_todas_cenas_resolvidas_localmente(
        self, banco_local_temporario: Path, monkeypatch
    ):
        monkeypatch.setattr(
            "services.visual.asset_resolver.BANCO_LOCAL_DIR",
            banco_local_temporario,
        )
        _recarregar_indice()

        metadata = MetadataRoteiro(
            video_id="test_local_only",
            nicho="cultura_pop",
            titulo_sugerido="Teste Local",
            duracao_estimada_segundos=10.0,
            trilha_fundo="music.mp3",
        )

        cena1 = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Doctor Doom é incrível.",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["doctor_doom"],
                fallback_query="doctor doom",
                duracao_minima=3.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            ),
            overlays=Overlays(exibir_legenda=True),
        )

        cena2 = Cena(
            cena_id=2,
            ordem=2,
            texto_locucao="Naruto é um anime popular.",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.video,
                keywords_busca=["naruto"],
                fallback_query="naruto anime",
                duracao_minima=3.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.pan_lateral,
            ),
            overlays=Overlays(exibir_legenda=True),
        )

        roteiro = Roteiro(metadata=metadata, cenas=[cena1, cena2])
        resultado = await resolver_assets_do_roteiro(roteiro)

        assert all(c.asset_resolvido_path for c in resultado.cenas)
        assert all(c.asset_origem == "banco_local" for c in resultado.cenas)
        assert not any(c.revisao_manual_necessaria for c in resultado.cenas)


# ---------------------------------------------------------------------------
# Testes do fallback_scraper (Pexels mockado)
# ---------------------------------------------------------------------------

class TestFallbackScraper:
    """Testes para o fallback via Pexels (mockado)."""

    @pytest.mark.asyncio
    async def test_pexels_sem_api_key(self, monkeypatch):
        from services.visual.fallback_scraper import buscar_asset_externo

        # Mocka settings sem API key
        mock_settings = MagicMock()
        mock_settings.pexels_api_key = None
        monkeypatch.setattr(
            "services.visual.fallback_scraper.settings",
            mock_settings,
        )

        resultado = await buscar_asset_externo(
            keywords=["test"],
            fallback_query="test query",
            tipo_asset="imagem",
        )

        assert resultado is None

    @pytest.mark.asyncio
    async def test_pexels_api_retorna_vazio(self, monkeypatch):
        from services.visual.fallback_scraper import buscar_asset_externo

        mock_settings = MagicMock()
        mock_settings.pexels_api_key = "fake_key"
        monkeypatch.setattr(
            "services.visual.fallback_scraper.settings",
            mock_settings,
        )

        # Mocka a resposta do httpx
        mock_response = MagicMock()
        mock_response.json.return_value = {"photos": []}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            resultado = await buscar_asset_externo(
                keywords=["test"],
                fallback_query="test query",
                tipo_asset="imagem",
            )

            assert resultado is None

    @pytest.mark.asyncio
    async def test_pexels_baixa_imagem(self, monkeypatch, tmp_path: Path):
        from services.visual.fallback_scraper import buscar_asset_externo, CACHE_DIR

        mock_settings = MagicMock()
        mock_settings.pexels_api_key = "fake_key"
        monkeypatch.setattr(
            "services.visual.fallback_scraper.settings",
            mock_settings,
        )
        monkeypatch.setattr(
            "services.visual.fallback_scraper.CACHE_DIR",
            tmp_path / "_fallback_cache",
        )

        # Mocka resposta da API
        mock_api_response = MagicMock()
        mock_api_response.json.return_value = {
            "photos": [
                {
                    "id": 12345,
                    "src": {
                        "large": "https://example.com/image.jpg",
                        "original": "https://example.com/image_orig.jpg",
                    },
                }
            ]
        }
        mock_api_response.raise_for_status = MagicMock()

        # Mocka resposta do download
        mock_download_response = MagicMock()
        mock_download_response.content = b"fake_image_content"
        mock_download_response.headers = {"content-type": "image/jpeg"}
        mock_download_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock()
            mock_get.side_effect = [mock_api_response, mock_download_response]
            mock_client.return_value.__aenter__.return_value.get = mock_get

            resultado = await buscar_asset_externo(
                keywords=["test"],
                fallback_query="test query",
                tipo_asset="imagem",
            )

            assert resultado is not None
            assert resultado.origem == "fallback_pexels"
            assert resultado.path.exists()
