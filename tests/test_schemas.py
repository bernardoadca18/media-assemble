"""Teste básico de sanidade dos schemas — valida que a Fase 1 tem uma base testável."""
from pipeline.schemas import Ideia, RespostaIdeacao


def test_resposta_ideacao_exige_cinco_ideias():
    ideia = Ideia(topico="Teste", titulo_sugerido="Titulo Teste", descricao_breve="Desc")
    try:
        RespostaIdeacao(ideias=[ideia])  # apenas 1, deve falhar
        assert False, "Deveria ter levantado ValidationError com menos de 5 ideias"
    except Exception:
        pass

    resposta = RespostaIdeacao(ideias=[ideia] * 5)
    assert len(resposta.ideias) == 5
