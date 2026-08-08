"""
Testes para Subfase 8.4 — Estilo Visual Vox.

Valida:
- Schemas com estilo_visual e elemento_grafico
- Serialização/deserialização com backward compatibility
- Renderização mista (ken_burns + vox_motion)
"""
import json
import pytest

from pipeline.schemas import (
    Cena,
    Midia,
    EfeitosVisuais,
    Overlays,
    AnimacaoImagem,
    TipoAsset,
    ComparacaoNumerica,
    LinhaDoTempo,
    Citacao,
    GraficoComparativo,
    Roteiro,
    MetadataRoteiro,
)


class TestSchemaEstiloVisual:
    """Testa os novos campos de estilo visual no schema Cena."""

    def test_cena_default_ken_burns(self):
        """Cena sem estilo_visual especificado deve usar ken_burns."""
        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["teste"],
                fallback_query="test",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            ),
            overlays=Overlays(),
        )
        assert cena.estilo_visual == "ken_burns"
        assert cena.elemento_grafico is None

    def test_cena_vox_motion_com_elemento(self):
        """Cena vox_motion deve aceitar elemento_grafico."""
        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["teste"],
                fallback_query="test",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            ),
            overlays=Overlays(),
            estilo_visual="vox_motion",
            elemento_grafico=ComparacaoNumerica(
                valor_principal="150M",
                rotulo_principal="views",
            ),
        )
        assert cena.estilo_visual == "vox_motion"
        assert cena.elemento_grafico is not None
        assert cena.elemento_grafico.valor_principal == "150M"

    def test_elemento_grafico_comparacao_numerica(self):
        """Testa ComparacaoNumerica com e sem valor de comparação."""
        comp = ComparacaoNumerica(
            valor_principal="100",
            rotulo_principal="milhões",
            valor_comparacao="50",
            rotulo_comparacao="anos atrás",
            unidade="%"
        )
        assert comp.valor_principal == "100"
        assert comp.unidade == "%"

        # Serialização
        data = comp.model_dump()
        assert data["valor_principal"] == "100"
        assert data["valor_comparacao"] == "50"

    def test_elemento_grafico_linha_do_tempo(self):
        """Testa LinhaDoTempo com eventos."""
        linha = LinhaDoTempo(
            eventos=["Evento 1", "Evento 2", "Evento 3"],
            ano_inicio="2020",
            ano_fim="2024",
            titulo="Timeline de eventos"
        )
        assert len(linha.eventos) == 3
        assert linha.ano_inicio == "2020"

    def test_elemento_grafico_linha_do_tempo_minimo_2_eventos(self):
        """LinhaDoTempo deve exigir pelo menos 2 eventos."""
        with pytest.raises(Exception):  # ValidationError
            LinhaDoTempo(eventos=["Apenas um"])

    def test_elemento_grafico_citacao(self):
        """Testa Citacao com autor e contexto."""
        citacao = Citacao(
            texto="A imaginação é mais importante que o conhecimento.",
            autor="Albert Einstein",
            contexto="Entrevista em 1929"
        )
        assert citacao.autor == "Albert Einstein"
        assert citacao.contexto == "Entrevista em 1929"

    def test_elemento_grafico_grafico_comparativo(self):
        """Testa GraficoComparativo com itens e valores."""
        grafico = GraficoComparativo(
            itens=["Python", "JavaScript", "Rust"],
            valores=["100", "90", "80"],
            titulo="Popularidade de Linguagens",
            unidade="%"
        )
        assert len(grafico.itens) == 3
        assert len(grafico.valores) == 3


class TestSerializacaoBackwardCompatibility:
    """Testa backward compatibility com roteiros antigos."""

    def test_deserializacao_roteiro_antigo_sem_estilo_visual(self):
        """Roteiro JSON sem estilo_visual deve usar default ken_burns."""
        roteiro_json = {
            "metadata": {
                "video_id": "test_123",
                "nicho": "cultura_pop",
                "titulo_sugerido": "Teste",
                "duracao_estimada_segundos": 60.0,
                "trilha_fundo": "epica",
                "volume_trilha_fundo": 0.15,
                "audio_final_path": None,
                "palavras_transcritas": None,
                "video_final_path": None,
            },
            "cenas": [
                {
                    "cena_id": 1,
                    "ordem": 1,
                    "texto_locucao": "Teste",
                    "duracao_estimada_segundos": 5.0,
                    "midia": {
                        "tipo_asset_preferencial": "imagem",
                        "keywords_busca": ["teste"],
                        "fallback_query": "test",
                        "duracao_minima": 5.0,
                    },
                    "efeitos_visuais": {
                        "animacao_imagem": "ken_burns_zoom_in",
                        "transicao_saida": "fade",
                        "duracao_transicao_segundos": 0.5,
                    },
                    "overlays": {
                        "exibir_legenda": True,
                        "texto_destaque_tela": None,
                    },
                    # Note: sem estilo_visual e sem elemento_grafico
                    "audio_path": None,
                    "palavras_transcritas": None,
                    "wer_final": None,
                    "revisao_manual_necessaria": False,
                    "asset_resolvido_path": None,
                    "asset_origem": None,
                }
            ],
        }

        roteiro = Roteiro.model_validate(roteiro_json)
        assert roteiro.cenas[0].estilo_visual == "ken_burns"
        assert roteiro.cenas[0].elemento_grafico is None

    def test_serializacao_preserva_estilo_visual(self):
        """Serialização deve incluir estilo_visual e elemento_grafico."""
        cena = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Teste",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["teste"],
                fallback_query="test",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            ),
            overlays=Overlays(),
            estilo_visual="vox_motion",
            elemento_grafico=LinhaDoTempo(
                eventos=["A", "B"],
                titulo="Teste"
            ),
        )

        json_str = cena.model_dump_json()
        data = json.loads(json_str)

        assert data["estilo_visual"] == "vox_motion"
        assert data["elemento_grafico"]["eventos"] == ["A", "B"]


class TestRoteiroMisto:
    """Testa roteiro com cenas mistas (ken_burns + vox_motion)."""

    def test_roteiro_com_cenas_mistas(self):
        """Roteiro pode ter cenas com diferentes estilos visuais."""
        metadata = MetadataRoteiro(
            video_id="teste_misto",
            nicho="cultura_pop",
            titulo_sugerido="Teste Misto",
            duracao_estimada_segundos=30.0,
            trilha_fundo="epica",
            volume_trilha_fundo=0.15,
        )

        cena_ken_burns = Cena(
            cena_id=1,
            ordem=1,
            texto_locucao="Cena narrativa",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["lore"],
                fallback_query="fantasy",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
            ),
            overlays=Overlays(),
            estilo_visual="ken_burns",
        )

        cena_vox_motion = Cena(
            cena_id=2,
            ordem=2,
            texto_locucao="Cena de dados",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["data"],
                fallback_query="statistics",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=AnimacaoImagem.pan_lateral,
            ),
            overlays=Overlays(),
            estilo_visual="vox_motion",
            elemento_grafico=ComparacaoNumerica(
                valor_principal="1B",
                rotulo_principal="views",
            ),
        )

        roteiro = Roteiro(
            metadata=metadata,
            cenas=[cena_ken_burns, cena_vox_motion],
        )

        assert len(roteiro.cenas) == 2
        assert roteiro.cenas[0].estilo_visual == "ken_burns"
        assert roteiro.cenas[1].estilo_visual == "vox_motion"
        assert roteiro.cenas[0].elemento_grafico is None
        assert roteiro.cenas[1].elemento_grafico is not None

    def test_serializacao_roteiro_misto(self):
        """Serialização de roteiro misto deve preservar estilos."""
        metadata = MetadataRoteiro(
            video_id="teste_misto_2",
            nicho="tecnologia",
            titulo_sugerido="Teste Misto 2",
            duracao_estimada_segundos=20.0,
            trilha_fundo="suspense",
            volume_trilha_fundo=0.15,
        )

        cenas = [
            Cena(
                cena_id=i,
                ordem=i,
                texto_locucao=f"Cena {i}",
                duracao_estimada_segundos=5.0,
                midia=Midia(
                    tipo_asset_preferencial=TipoAsset.imagem,
                    keywords_busca=[f"keyword{i}"],
                    fallback_query="test",
                    duracao_minima=5.0,
                ),
                efeitos_visuais=EfeitosVisuais(
                    animacao_imagem=AnimacaoImagem.ken_burns_zoom_in,
                ),
                overlays=Overlays(),
                estilo_visual="vox_motion" if i % 2 == 0 else "ken_burns",
                elemento_grafico=Citacao(
                    texto=f"Citação {i}",
                    autor="Autor"
                ) if i % 2 == 0 else None,
            )
            for i in range(1, 5)
        ]

        roteiro = Roteiro(metadata=metadata, cenas=cenas)

        # Serializar e deserializar
        json_str = roteiro.model_dump_json()
        data = json.loads(json_str)
        roteiro_restaurado = Roteiro.model_validate(data)

        # Verificar estilos foram preservados
        for i, cena in enumerate(roteiro_restaurado.cenas):
            expected_style = "vox_motion" if (i + 1) % 2 == 0 else "ken_burns"
            assert cena.estilo_visual == expected_style
            if expected_style == "vox_motion":
                assert cena.elemento_grafico is not None


class TestValidacaoElementoGrafico:
    """Testa validações dos elementos gráficos."""

    def test_comparacao_numerica_minimo(self):
        """ComparacaoNumerica pode ter apenas valor_principal e rotulo."""
        comp = ComparacaoNumerica(
            valor_principal="100",
            rotulo_principal="unidades",
        )
        assert comp.valor_comparacao is None
        assert comp.unidade == ""

    def test_grafico_comparativo_minimo_2_itens(self):
        """GraficoComparativo deve ter pelo menos 2 itens."""
        with pytest.raises(Exception):
            GraficoComparativo(
                itens=["Apenas um"],
                valores=["100"],
                titulo="Teste"
            )

    def test_grafico_comparativo_maximo_6_itens(self):
        """GraficoComparativo não pode ter mais de 6 itens."""
        with pytest.raises(Exception):
            GraficoComparativo(
                itens=["A", "B", "C", "D", "E", "F", "G"],
                valores=["1", "2", "3", "4", "5", "6", "7"],
                titulo="Teste"
            )
