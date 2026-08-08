"""
Testes para Subfase 8.5 — Suporte a Shorts.

Valida:
- Schema com formato e video_origem_id
- Validação de duração para shorts (25-58s)
- Criação de roteiro short nativo
- Seleção de clips a partir de vídeo longo
- Renderização vertical
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from pipeline.schemas import (
    Roteiro,
    MetadataRoteiro,
    Cena,
    Midia,
    EfeitosVisuais,
    Overlays,
    AnimacaoImagem,
    TipoAsset,
)
from pipeline.nichos import obter_config_nicho


class TestSchemaShorts:
    """Testa campos de shorts no schema."""

    def test_metadata_formato_default_longo(self):
        """Metadata sem formato deve usar default 'longo'."""
        metadata = MetadataRoteiro(
            video_id="test_123",
            nicho="cultura_pop",
            titulo_sugerido="Teste",
            duracao_estimada_segundos=180.0,
            trilha_fundo="epica",
        )
        assert metadata.formato == "longo"
        assert metadata.video_origem_id is None

    def test_metadata_formato_short_valido(self):
        """Metadata com formato short e duração válida."""
        metadata = MetadataRoteiro(
            video_id="test_short",
            nicho="cultura_pop",
            titulo_sugerido="Short Teste",
            duracao_estimada_segundos=45.0,
            trilha_fundo="epica",
            formato="short",
        )
        assert metadata.formato == "short"

    def test_metadata_short_duracao_menor_25s_invalida(self):
        """Short com menos de 25s deve falhar."""
        with pytest.raises(ValueError, match="25s e 58s"):
            MetadataRoteiro(
                video_id="test_short",
                nicho="cultura_pop",
                titulo_sugerido="Short Muito Curto",
                duracao_estimada_segundos=20.0,
                trilha_fundo="epica",
                formato="short",
            )

    def test_metadata_short_duracao_maior_58s_invalida(self):
        """Short com mais de 58s deve falhar."""
        with pytest.raises(ValueError, match="25s e 58s"):
            MetadataRoteiro(
                video_id="test_short",
                nicho="cultura_pop",
                titulo_sugerido="Short Muito Longo",
                duracao_estimada_segundos=60.0,
                trilha_fundo="epica",
                formato="short",
            )

    def test_metadata_short_limites_validos(self):
        """Short nos limites exatos (25s e 58s) deve ser válido."""
        # Limite mínimo
        metadata_min = MetadataRoteiro(
            video_id="test_short_min",
            nicho="cultura_pop",
            titulo_sugerido="Short 25s",
            duracao_estimada_segundos=25.0,
            trilha_fundo="epica",
            formato="short",
        )
        assert metadata_min.formato == "short"

        # Limite máximo
        metadata_max = MetadataRoteiro(
            video_id="test_short_max",
            nicho="cultura_pop",
            titulo_sugerido="Short 58s",
            duracao_estimada_segundos=58.0,
            trilha_fundo="epica",
            formato="short",
        )
        assert metadata_max.formato == "short"

    def test_metadata_video_origem_id(self):
        """Short derivado deve ter video_origem_id."""
        metadata = MetadataRoteiro(
            video_id="test_short_derivado",
            nicho="cultura_pop",
            titulo_sugerido="Short Derivado",
            duracao_estimada_segundos=40.0,
            trilha_fundo="epica",
            formato="short",
            video_origem_id="video_longo_123",
        )
        assert metadata.video_origem_id == "video_longo_123"


class TestConfigNichoShorts:
    """Testa configuração de shorts por nicho."""

    def test_todos_nichos_tem_prompt_short(self):
        """Todos os nichos devem ter prompt_roteiro_short configurado."""
        from pipeline.nichos import NICHOS_CONFIG

        for nicho_nome, config in NICHOS_CONFIG.items():
            assert hasattr(config, "prompt_roteiro_short")
            assert config.prompt_roteiro_short is not None
            assert len(config.prompt_roteiro_short) > 50
            assert "gancho" in config.prompt_roteiro_short.lower()

    def test_prompt_short_cultura_pop(self):
        """Prompt de short para cultura_pop tem diretrizes corretas."""
        config = obter_config_nicho("cultura_pop")
        prompt = config.prompt_roteiro_short

        assert "1-2 segundos" in prompt or "1-2s" in prompt
        assert "replay" in prompt.lower()

    def test_prompt_short_tecnologia(self):
        """Prompt de short para tecnologia tem diretrizes corretas."""
        config = obter_config_nicho("tecnologia")
        prompt = config.prompt_roteiro_short

        assert "gancho" in prompt.lower()
        assert "4-8 cenas" in prompt

    def test_prompt_short_futebol(self):
        """Prompt de short para futebol tem diretrizes corretas."""
        config = obter_config_nicho("futebol")
        prompt = config.prompt_roteiro_short

        assert "gancho" in prompt.lower()
        assert "25-58 segundos" in prompt


class TestClipSelector:
    """Testa seleção de clips a partir de vídeos longos."""

    @pytest.fixture
    def roteiro_longo_exemplo(self) -> Roteiro:
        """Cria um roteiro longo de exemplo para testes."""
        metadata = MetadataRoteiro(
            video_id="video_longo_123",
            nicho="cultura_pop",
            titulo_sugerido="A História Completa de Naruto",
            duracao_estimada_segundos=180.0,
            trilha_fundo="epica",
        )

        cenas = [
            Cena(
                cena_id=i,
                ordem=i,
                texto_locucao=f"Cena {i} do vídeo longo com conteúdo interessante.",
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
            for i in range(1, 19)  # 18 cenas de 10s = 180s
        ]

        return Roteiro(metadata=metadata, cenas=cenas)

    @pytest.mark.asyncio
    async def test_selecionar_clips_sucesso(self, roteiro_longo_exemplo):
        """Testa seleção de clips com LLM mockado."""
        from services.scripting.clip_selector import selecionar_clips

        mock_resposta = '''
        {
          "clips": [
            {
              "cena_inicio_id": 1,
              "cena_fim_id": 4,
              "titulo_sugerido": "O Segredo de Naruto que Você Não Sabia",
              "justificativa": "Trecho com gancho forte e revelação impactante"
            },
            {
              "cena_inicio_id": 10,
              "cena_fim_id": 14,
              "titulo_sugerido": "O Momento Mais Trágico do Anime",
              "justificativa": "Momento emocional que funciona isolado"
            }
          ]
        }
        '''

        with patch(
            "services.scripting.clip_selector.complete_cloud",
            new_callable=AsyncMock,
            return_value=mock_resposta,
        ):
            clips = await selecionar_clips(roteiro_longo_exemplo, num_clips=2)

        assert len(clips) == 2
        assert clips[0]["cena_inicio_id"] == 1
        assert clips[0]["cena_fim_id"] == 4
        assert "titulo_sugerido" in clips[0]

    def test_criar_roteiro_clip_duracao_valida(self, roteiro_longo_exemplo):
        """Testa criação de roteiro clip com duração válida."""
        from services.scripting.clip_selector import criar_roteiro_clip

        # Cena 1-4 = 40 segundos (dentro do limite)
        roteiro_short = criar_roteiro_clip(
            roteiro_longo=roteiro_longo_exemplo,
            cena_inicio_id=1,
            cena_fim_id=4,
            titulo_sugerido="Clip Teste",
        )

        assert roteiro_short.metadata.formato == "short"
        assert roteiro_short.metadata.video_origem_id == "video_longo_123"
        assert roteiro_short.metadata.duracao_estimada_segundos == 40.0
        assert len(roteiro_short.cenas) == 4
        assert roteiro_short.metadata.video_id.startswith("video_longo_123_clip_")

    def test_criar_roteiro_clip_duracao_invalida_menor(self, roteiro_longo_exemplo):
        """Testa criação de clip com duração menor que 25s."""
        from services.scripting.clip_selector import criar_roteiro_clip

        # Cena 1-2 = 20 segundos (menor que 25s)
        with pytest.raises(ValueError, match="25s e 58s"):
            criar_roteiro_clip(
                roteiro_longo=roteiro_longo_exemplo,
                cena_inicio_id=1,
                cena_fim_id=2,
                titulo_sugerido="Clip Muito Curto",
            )

    def test_criar_roteiro_clip_duracao_invalida_maior(self, roteiro_longo_exemplo):
        """Testa criação de clip com duração maior que 58s."""
        from services.scripting.clip_selector import criar_roteiro_clip

        # Cena 1-7 = 70 segundos (maior que 58s)
        with pytest.raises(ValueError, match="25s e 58s"):
            criar_roteiro_clip(
                roteiro_longo=roteiro_longo_exemplo,
                cena_inicio_id=1,
                cena_fim_id=7,
                titulo_sugerido="Clip Muito Longo",
            )

    def test_criar_roteiro_clip_reaproveita_assets(self, roteiro_longo_exemplo):
        """Testa que clip reaproveita assets do vídeo original."""
        from services.scripting.clip_selector import criar_roteiro_clip

        roteiro_short = criar_roteiro_clip(
            roteiro_longo=roteiro_longo_exemplo,
            cena_inicio_id=5,
            cena_fim_id=8,
            titulo_sugerido="Clip com Assets",
        )

        # Verificar que assets foram reaproveitados
        for cena in roteiro_short.cenas:
            assert cena.asset_resolvido_path is not None
            assert "naruto_" in cena.asset_resolvido_path

    def test_criar_roteiro_clip_reordena_cenas(self, roteiro_longo_exemplo):
        """Testa que cenas do clip são reordenadas sequencialmente."""
        from services.scripting.clip_selector import criar_roteiro_clip

        roteiro_short = criar_roteiro_clip(
            roteiro_longo=roteiro_longo_exemplo,
            cena_inicio_id=10,
            cena_fim_id=13,
            titulo_sugerido="Clip Reordenado",
        )

        # Verificar ordenação sequencial
        for i, cena in enumerate(roteiro_short.cenas):
            assert cena.cena_id == i + 1
            assert cena.ordem == i + 1


class TestRenderizacaoShort:
    """Testa renderização de shorts."""

    @pytest.fixture
    def roteiro_short_exemplo(self) -> Roteiro:
        """Cria um roteiro short de exemplo."""
        metadata = MetadataRoteiro(
            video_id="short_test_123",
            nicho="tecnologia",
            titulo_sugerido="Por que Rust está Substituindo C++",
            duracao_estimada_segundos=45.0,
            trilha_fundo="suspense",
            formato="short",
        )

        cenas = [
            Cena(
                cena_id=i,
                ordem=i,
                texto_locucao=f"Ponto {i} sobre Rust.",
                duracao_estimada_segundos=9.0,
                midia=Midia(
                    tipo_asset_preferencial=TipoAsset.imagem,
                    keywords_busca=["rust", "programming"],
                    fallback_query="code",
                    duracao_minima=9.0,
                ),
                efeitos_visuais=EfeitosVisuais(
                    animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
                ),
                overlays=Overlays(),
                asset_resolvido_path=f"assets/rust_{i}.jpg",
            )
            for i in range(1, 6)  # 5 cenas de 9s = 45s
        ]

        return Roteiro(metadata=metadata, cenas=cenas)

    @pytest.mark.asyncio
    async def test_renderizar_video_short_composicao_correta(self, roteiro_short_exemplo):
        """Testa que renderização usa composição VideoShort."""
        from services.render.remotion_bridge import renderizar_video_short

        with patch(
            "services.render.remotion_bridge._executar_comando_remotion"
        ) as mock_exec:
            mock_exec.return_value = {
                "returncode": 0,
                "stdout": "Render completed",
                "stderr": "",
            }

            with patch("services.render.remotion_bridge.settings") as mock_settings:
                mock_settings.data_dir = MagicMock()
                mock_settings.data_dir.__truediv__ = MagicMock(return_value=MagicMock())
                mock_settings.remotion_dir = "/tmp/remotion"
                mock_settings.remotion_concurrency = 1

                with patch("pathlib.Path.mkdir"):
                    with patch("pathlib.Path.touch"):
                        with patch("tempfile.NamedTemporaryFile"):
                            resultado = await renderizar_video_short(roteiro_short_exemplo)

            # Verificar que comando foi chamado com VideoShort
            args = mock_exec.call_args[0]
            comando = args[0]
            assert "VideoShort" in comando

    def test_roteiro_short_serializacao(self, roteiro_short_exemplo):
        """Testa serialização de roteiro short."""
        json_str = roteiro_short_exemplo.model_dump_json()
        data = __import__("json").loads(json_str)

        assert data["metadata"]["formato"] == "short"
        assert data["metadata"]["duracao_estimada_segundos"] == 45.0
        assert len(data["cenas"]) == 5


class TestOrquestracaoShorts:
    """Testa integração de shorts no orquestrador."""

    def test_should_generate_shorts_desativado(self):
        """Testa verificação quando shorts estão desativados."""
        from pipeline.orchestrator import _should_generate_shorts

        with patch.dict("os.environ", {"GERAR_SHORTS_AUTOMATICO": "false"}):
            result = _should_generate_shorts("cultura_pop")
            assert result is False

    def test_should_generate_shorts_ativado(self):
        """Testa verificação quando shorts estão ativados."""
        from pipeline.orchestrator import _should_generate_shorts

        with patch.dict("os.environ", {"GERAR_SHORTS_AUTOMATICO": "true"}):
            result = _should_generate_shorts("cultura_pop")
            assert result is True

    def test_should_generate_shorts_nicho_sem_prompt(self):
        """Testa verificação para nicho sem prompt de short."""
        from pipeline.orchestrator import _should_generate_shorts

        # Como todos os nichos agora têm prompt, testamos com exception handling
        with patch.dict("os.environ", {"GERAR_SHORTS_AUTOMATICO": "true"}):
            with patch(
                "pipeline.nichos.obter_config_nicho",
                side_effect=ValueError("Nicho inexistente")
            ):
                result = _should_generate_shorts("nicho_inexistente")
                assert result is False


class TestBackwardCompatibility:
    """Testa compatibilidade com roteiros antigos."""

    def test_roteiro_antigo_sem_formato_serializa(self):
        """Roteiro antigo sem campo formato deve serializar corretamente."""
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
                # Sem campo formato e video_origem_id
            },
            "cenas": [],
        }

        roteiro = Roteiro.model_validate(roteiro_json)
        assert roteiro.metadata.formato == "longo"
        assert roteiro.metadata.video_origem_id is None
