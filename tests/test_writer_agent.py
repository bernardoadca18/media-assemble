"""Testes para o agente de roteirização (Fase 2)."""
import json
import pytest
from unittest.mock import AsyncMock, patch

from pipeline.schemas import (
    Ideia,
    Roteiro,
    Cena,
    MetadataRoteiro,
    Midia,
    EfeitosVisuais,
    Overlays,
    TipoAsset,
    AnimacaoImagem,
)
from services.scripting.writer_agent import (
    gerar_roteiro,
    _limpar_resposta_json,
    _validar_regras_negocio,
)


# Fixture de ideia para testes
IDEIA_TESTE = Ideia(
    topico="Naruto",
    titulo_sugerido="Os Clãs Mais Poderosos de Naruto Explicados",
    descricao_breve="Análise completa dos clãs mais fortes de Naruto e suas habilidades únicas",
)


# Fixture de roteiro válido para testes
def criar_roteiro_valido(video_id="abc12345", num_cenas=20):
    """Cria um roteiro válido para testes."""
    cenas = []
    animacoes = [
        AnimacaoImagem.ken_burns_zoom_in,
        AnimacaoImagem.ken_burns_zoom_out,
        AnimacaoImagem.pan_lateral,
    ]

    for i in range(1, num_cenas + 1):
        # Variar animações sem repetir 3x seguidas
        anim = animacoes[i % 3]

        cena = Cena(
            cena_id=i,
            ordem=i,
            texto_locucao=f"Texto da cena {i} sobre o clã Uchiha e suas habilidades.",
            duracao_estimada_segundos=5.0,
            midia=Midia(
                tipo_asset_preferencial=TipoAsset.imagem,
                keywords_busca=["Naruto Uchiha", "Sharingan"],
                fallback_query="Naruto anime clan",
                duracao_minima=5.0,
            ),
            efeitos_visuais=EfeitosVisuais(
                animacao_imagem=anim,
                transicao_saida="fade",
                duracao_transicao_segundos=0.5,
            ),
            overlays=Overlays(
                exibir_legenda=True,
                texto_destaque_tela="Uchiha Clan" if i % 4 == 0 else None,
            ),
        )
        cenas.append(cena)

    return Roteiro(
        metadata=MetadataRoteiro(
            video_id=video_id,
            nicho="cultura_pop",
            titulo_sugerido="Os Clãs Mais Poderosos de Naruto Explicados",
            duracao_estimada_segundos=float(num_cenas * 5),
            trilha_fundo="epica",
            volume_trilha_fundo=0.15,
        ),
        cenas=cenas,
    )


# Resposta JSON mockada válida
def criar_json_roteiro_valido(video_id="abc12345"):
    """Cria um JSON de roteiro válido para mockar resposta do LLM."""
    roteiro = criar_roteiro_valido(video_id)
    return roteiro.model_dump_json()


# Resposta JSON mockada inválida (para testar retry)
JSON_ROTEIRO_INVALIDO = """
{
  "metadata": {
    "video_id": "invalid123",
    "nicho": "cultura_pop",
    "titulo_sugerido": "Teste Inválido"
  },
  "cenas": [
    {
      "cena_id": 1,
      "ordem": 1,
      "texto_locucao": "Texto muito curto",
      "duracao_estimada_segundos": 1.0
    }
  ]
}
"""


class TestLimparRespostaJson:
    """Testes para a função de limpeza de resposta JSON."""

    def test_remove_bloco_markdown_json(self):
        """Remove bloco ```json ... ```."""
        texto = '```json\n{"teste": 1}\n```'
        resultado = _limpar_resposta_json(texto)
        assert resultado == '{"teste": 1}'

    def test_remove_bloco_markdown_generico(self):
        """Remove bloco ``` ... ```."""
        texto = '```\n{"teste": 1}\n```'
        resultado = _limpar_resposta_json(texto)
        assert resultado == '{"teste": 1}'

    def test_mantem_json_puro(self):
        """Mantém JSON sem markdown."""
        texto = '{"teste": 1}'
        resultado = _limpar_resposta_json(texto)
        assert resultado == '{"teste": 1}'


class TestValidarRegrasNegocio:
    """Testes para validação de regras de negócio."""

    def test_roteiro_valido_sem_erros(self):
        """Roteiro válido não gera erros."""
        roteiro = criar_roteiro_valido()
        erros = _validar_regras_negocio(roteiro)
        assert erros == []

    def test_poucas_cenas_gera_erro(self):
        """Roteiro com menos de 10 cenas gera erro."""
        roteiro = criar_roteiro_valido(num_cenas=5)
        erros = _validar_regras_negocio(roteiro)
        assert any("Poucas cenas" in e for e in erros)

    def test_cena_curta_demais_gera_erro(self):
        """Cena com menos de 3 segundos gera erro."""
        roteiro = criar_roteiro_valido(num_cenas=1)
        roteiro.cenas[0].duracao_estimada_segundos = 2.0
        erros = _validar_regras_negocio(roteiro)
        assert any("muito curta" in e for e in erros)

    def test_cena_longa_demais_gera_erro(self):
        """Cena com mais de 8 segundos gera erro."""
        roteiro = criar_roteiro_valido(num_cenas=1)
        roteiro.cenas[0].duracao_estimada_segundos = 10.0
        erros = _validar_regras_negocio(roteiro)
        assert any("muito longa" in e for e in erros)

    def test_animacao_repetida_3x_gera_erro(self):
        """Animação repetida 3x consecutivas gera erro."""
        roteiro = criar_roteiro_valido(num_cenas=3)
        # Todas com a mesma animação
        for cena in roteiro.cenas:
            cena.efeitos_visuais.animacao_imagem = AnimacaoImagem.ken_burns_zoom_in

        erros = _validar_regras_negocio(roteiro)
        assert any("repetida 3 vezes" in e for e in erros)

    def test_texto_destaque_excessivo_gera_erro(self):
        """Texto_destaque_tela em mais de 1/3 das cenas gera erro."""
        roteiro = criar_roteiro_valido(num_cenas=10)
        # Colocar destaque em todas as cenas
        for cena in roteiro.cenas:
            cena.overlays.texto_destaque_tela = "Destaque"

        erros = _validar_regras_negocio(roteiro)
        assert any("Texto_destaque_tela usado em" in e for e in erros)


class TestGerarRoteiro:
    """Testes para a função principal gerar_roteiro."""

    @pytest.mark.asyncio
    async def test_geracao_sucesso_primeira_tentativa(self):
        """Gera roteiro válido na primeira tentativa."""
        json_valido = criar_json_roteiro_valido()

        with patch(
            "services.scripting.writer_agent.complete_cloud",
            new_callable=AsyncMock,
            return_value=json_valido,
        ):
            roteiro = await gerar_roteiro(ideia=IDEIA_TESTE)

        assert isinstance(roteiro, Roteiro)
        assert len(roteiro.cenas) >= 10
        assert roteiro.metadata.video_id is not None

    @pytest.mark.asyncio
    async def test_retry_sucesso_segunda_tentativa(self):
        """Retry funciona quando primeira tentativa falha."""
        json_invalido = '{"metadata": {}, "cenas": []}'  # JSON válido mas schema inválido
        json_valido = criar_json_roteiro_valido()

        with patch(
            "services.scripting.writer_agent.complete_cloud",
            new_callable=AsyncMock,
            side_effect=[json_invalido, json_valido],
        ):
            roteiro = await gerar_roteiro(ideia=IDEIA_TESTE, max_tentativas=3)

        assert isinstance(roteiro, Roteiro)
        assert len(roteiro.cenas) >= 10

    @pytest.mark.asyncio
    async def test_falha_apos_esgotar_tentativas(self):
        """Levanta RuntimeError após esgotar tentativas."""
        json_invalido = '{"metadata": {}, "cenas": []}'

        with patch(
            "services.scripting.writer_agent.complete_cloud",
            new_callable=AsyncMock,
            return_value=json_invalido,
        ):
            with pytest.raises(RuntimeError) as exc_info:
                await gerar_roteiro(ideia=IDEIA_TESTE, max_tentativas=2)

        assert "Falha ao gerar roteiro" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_video_id_unico_gerado(self):
        """Cada roteiro recebe um video_id único."""
        json_valido1 = criar_json_roteiro_valido("id1")
        json_valido2 = criar_json_roteiro_valido("id2")

        with patch(
            "services.scripting.writer_agent.complete_cloud",
            new_callable=AsyncMock,
            side_effect=[json_valido1, json_valido2],
        ):
            roteiro1 = await gerar_roteiro(ideia=IDEIA_TESTE)
            roteiro2 = await gerar_roteiro(ideia=IDEIA_TESTE)

        assert roteiro1.metadata.video_id != roteiro2.metadata.video_id


class TestPersistenciaRoteiro:
    """Testes para persistência de roteiros."""

    @pytest.mark.asyncio
    async def test_salvar_e_recuperar_roteiro(self):
        """Salva e recupera roteiro do banco."""
        from db.models import salvar_roteiro
        from unittest.mock import MagicMock

        roteiro_original = criar_roteiro_valido(video_id="test_persist_01")

        # Mock da sessão do banco
        mock_session_instance = AsyncMock()
        # O execute retorna um Result que tem scalar_one_or_none como método síncrono
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Não existe ainda
        mock_session_instance.execute.return_value = mock_result

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            # Salvar
            video_id = await salvar_roteiro(roteiro_original)
            assert video_id == roteiro_original.metadata.video_id

            # Verificar que commit foi chamado
            mock_session_instance.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_buscar_roteiro_inexistente(self):
        """Buscar roteiro inexistente retorna None."""
        from db.models import buscar_roteiro
        from unittest.mock import MagicMock

        mock_session_instance = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session_instance.execute.return_value = mock_result

        with patch("db.models.AsyncSessionLocal") as mock_session:
            mock_session.return_value.__aenter__.return_value = mock_session_instance

            resultado = await buscar_roteiro("video_inexistente")
            assert resultado is None


class TestIntegracaoOrchestrator:
    """Testes de integração com o orchestrator."""

    @pytest.mark.asyncio
    async def test_rodar_etapa_roteirizacao(self):
        """Testa a etapa de roteirização isolada."""
        from pipeline.orchestrator import rodar_etapa_roteirizacao
        from unittest.mock import MagicMock

        json_valido = criar_json_roteiro_valido()

        mock_session_instance = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session_instance.execute.return_value = mock_result

        with patch(
            "services.scripting.writer_agent.complete_cloud",
            new_callable=AsyncMock,
            return_value=json_valido,
        ):
            with patch("db.models.AsyncSessionLocal") as mock_session:
                mock_session.return_value.__aenter__.return_value = mock_session_instance

                roteiro = await rodar_etapa_roteirizacao(ideia=IDEIA_TESTE)

        assert isinstance(roteiro, Roteiro)
        assert len(roteiro.cenas) >= 10
