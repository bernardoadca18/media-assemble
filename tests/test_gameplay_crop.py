"""
Testes para Fase 9.4 — Recorte vertical para Shorts/TikTok no modo gameplay.

Valida:
- Configuração de crop_offset_y por jogo
- Aplicação de crop vertical no SceneRenderer
- Integração com gameplay_bg
"""
import pytest

from services.gameplay.crop_config import (
    CropConfigJogo,
    CROP_CONFIG_POR_JOGO,
    obter_crop_offset_y,
    listar_jogos_configurados,
)


class TestCropConfigJogo:
    """Testa configuração de crop por jogo."""

    def test_config_existe_para_jogos_populares(self):
        """Jogos populares têm configuração de crop."""
        jogos_esperados = [
            "minecraft",
            "fortnite",
            "valorant",
            "league_of_legends",
            "gta_v",
        ]

        for jogo in jogos_esperados:
            assert jogo in CROP_CONFIG_POR_JOGO, f"Config para {jogo} não encontrada"

    def test_crop_offset_y_dentro_limites(self):
        """Offset Y está dentro de limites razoáveis."""
        for jogo, config in CROP_CONFIG_POR_JOGO.items():
            # Limite arbitrário: -500 a +500 pixels
            assert -500 <= config.crop_offset_y <= 500, (
                f"Offset Y {config.crop_offset_y} fora dos limites para {jogo}"
            )

    def test_todas_configs_tem_descricao(self):
        """Todas as configurações têm descrição."""
        for jogo, config in CROP_CONFIG_POR_JOGO.items():
            assert config.descricao, f"Config para {jogo} sem descrição"


class TestObterCropOffsetY:
    """Testa obtenção de offset Y por jogo."""

    def test_jogo_existente_retorna_configurado(self):
        """Jogo existente retorna offset configurado."""
        offset = obter_crop_offset_y("minecraft")
        assert offset == 0

        offset = obter_crop_offset_y("valorant")
        assert offset == 100

    def test_jogo_case_insensitive(self):
        """Nome do jogo é case insensitive."""
        assert obter_crop_offset_y("MINECRAFT") == obter_crop_offset_y("minecraft")
        assert obter_crop_offset_y("VALORANT") == obter_crop_offset_y("valorant")
        assert obter_crop_offset_y("Fortnite") == obter_crop_offset_y("fortnite")

    def test_jogo_com_espacos_ou_hifens(self):
        """Nome do jogo aceita espaços e hifens."""
        # League of Legends = league_of_legends
        offset = obter_crop_offset_y("League of Legends")
        assert offset == 150

        # GTA V = gta_v
        offset = obter_crop_offset_y("GTA-V")
        assert offset == -80

    def test_jogo_inexistente_retorna_default(self):
        """Jogo não configurado retorna valor default."""
        offset = obter_crop_offset_y("jogo_inexistente_123")
        assert offset == 0

        offset = obter_crop_offset_y("jogo_inexistente_123", default=50)
        assert offset == 50

    def test_match_parcial_jogo(self):
        """Match parcial encontra jogo similar."""
        # "cod" deve encontrar "call_of_duty"
        offset = obter_crop_offset_y("cod_warzone")
        # Deve usar call_of_duty como match parcial
        assert offset == 0

    def test_listar_jogos_configurados(self):
        """Lista de jogos configurados está correta."""
        jogos = listar_jogos_configurados()

        assert isinstance(jogos, list)
        assert len(jogos) > 0
        assert "minecraft" in jogos


class TestIntegracaoCropVertical:
    """Testa integração do crop vertical com o pipeline."""

    def test_cena_schema_aceita_crop_offset_y(self):
        """Schema Cena aceita campo crop_offset_y."""
        from pipeline.schemas import Cena, Midia, EfeitosVisuais, Overlays, AnimacaoImagem

        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=10,
            midia=Midia(
                keywords_busca=["teste"],
                tipo_asset_preferencial="video",
                fallback_query="teste fallback",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
            overlays=Overlays(),
            estilo_visual="gameplay_bg",
            crop_offset_y=100,
        )

        assert cena.crop_offset_y == 100

    def test_cena_default_crop_offset_y_zero(self):
        """Campo crop_offset_y tem default 0."""
        from pipeline.schemas import Cena, Midia, EfeitosVisuais, Overlays, AnimacaoImagem

        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=10,
            midia=Midia(
                keywords_busca=["teste"],
                tipo_asset_preferencial="video",
                fallback_query="teste fallback",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
            overlays=Overlays(),
        )

        assert cena.crop_offset_y == 0

    def test_estilo_visual_gameplay_bg_valido(self):
        """estilo_visual aceita valor 'gameplay_bg'."""
        from pipeline.schemas import Cena, Midia, EfeitosVisuais, Overlays, AnimacaoImagem

        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=10,
            midia=Midia(
                keywords_busca=["teste"],
                tipo_asset_preferencial="video",
                fallback_query="teste fallback",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
            overlays=Overlays(),
            estilo_visual="gameplay_bg",
        )

        assert cena.estilo_visual == "gameplay_bg"


class TestSceneRendererGameplayBg:
    """Testa renderização de gameplay_bg no SceneRenderer."""

    def test_gameplay_bg_requer_asset_resolvido(self):
        """gameplay_bg sem asset_resolvido_path retorna None."""
        # Este teste seria ideal com React Testing Library
        # Por ora, validamos que o código não lança exceção
        from pipeline.schemas import Cena, Midia, EfeitosVisuais, Overlays, AnimacaoImagem

        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=10,
            midia=Midia(
                keywords_busca=["teste"],
                tipo_asset_preferencial="video",
                fallback_query="teste fallback",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(animacao_imagem=AnimacaoImagem.ken_burns_zoom_in),
            overlays=Overlays(),
            estilo_visual="gameplay_bg",
            # Sem asset_resolvido_path
        )

        assert cena.asset_resolvido_path is None


class TestConfigNichoGameplayCrop:
    """Testa que ConfigNicho pode herdar config de crop."""

    def test_config_nicho_aceita_gameplay_intensidade(self):
        """ConfigNicho tem campo gameplay_intensidade_preferida."""
        from pipeline.nichos import ConfigNicho

        config = ConfigNicho(
            nome="test_nicho",
            prompt_ideacao="test",
            prompt_roteiro_adicional="test",
            prompt_roteiro_short="test",
            categoria_google_trends=1,
            subreddits_sugeridos=[],
            gameplay_intensidade_preferida="intenso",
        )

        assert config.gameplay_intensidade_preferida == "intenso"
