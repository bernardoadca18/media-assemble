"""
Testes para Subfase 8.7 — Multi-nicho em Produção.

Valida:
- Configuração de novos nichos (financas, ciencia, historia)
- Todos os campos obrigatórios presentes (prompt_roteiro_short, subreddits_sugeridos)
- Categorias do Google Trends válidas
- Integração com gpu_lock
"""
import pytest

from pipeline.nichos import NICHOS_CONFIG, obter_config_nicho, ConfigNicho


class TestNovosNichos:
    """Testa configuração dos novos nichos adicionados na Subfase 8.7."""

    def test_nicho_financas_existe(self):
        """Nicho financas deve estar configurado."""
        assert "financas" in NICHOS_CONFIG
        config = obter_config_nicho("financas")
        assert config.nome == "financas"
        assert config.categoria_google_trends == 7  # Finance

    def test_nicho_ciencia_existe(self):
        """Nicho ciencia deve estar configurado."""
        assert "ciencia" in NICHOS_CONFIG
        config = obter_config_nicho("ciencia")
        assert config.nome == "ciencia"
        assert config.categoria_google_trends == 11  # Science

    def test_nicho_historia_existe(self):
        """Nicho historia deve estar configurado."""
        assert "historia" in NICHOS_CONFIG
        config = obter_config_nicho("historia")
        assert config.nome == "historia"
        assert config.categoria_google_trends == 24  # Society

    def test_total_nichos_6(self):
        """Pipeline deve ter 6 nichos configurados."""
        assert len(NICHOS_CONFIG) == 6
        expected = {"cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"}
        assert set(NICHOS_CONFIG.keys()) == expected


class TestCamposObrigatoriosNichos:
    """Valida que todos os nichos têm campos obrigatórios."""

    @pytest.mark.parametrize("nicho_nome", ["cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"])
    def test_todos_tem_prompt_ideacao(self, nicho_nome):
        """Todos os nichos devem ter prompt_ideacao."""
        config = obter_config_nicho(nicho_nome)
        assert config.prompt_ideacao is not None
        assert len(config.prompt_ideacao) > 100
        assert "{tendencias}" in config.prompt_ideacao
        assert "{historico}" in config.prompt_ideacao

    @pytest.mark.parametrize("nicho_nome", ["cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"])
    def test_todos_tem_prompt_roteiro_adicional(self, nicho_nome):
        """Todos os nichos devem ter prompt_roteiro_adicional."""
        config = obter_config_nicho(nicho_nome)
        assert config.prompt_roteiro_adicional is not None
        assert len(config.prompt_roteiro_adicional) > 50

    @pytest.mark.parametrize("nicho_nome", ["cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"])
    def test_todos_tem_prompt_roteiro_short(self, nicho_nome):
        """Todos os nichos devem ter prompt_roteiro_short (Subfase 8.5)."""
        config = obter_config_nicho(nicho_nome)
        assert config.prompt_roteiro_short is not None
        assert len(config.prompt_roteiro_short) > 50
        assert "gancho" in config.prompt_roteiro_short.lower()
        assert "25-58" in config.prompt_roteiro_short or "25s e 58s" in config.prompt_roteiro_short

    @pytest.mark.parametrize("nicho_nome", ["cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"])
    def test_todos_tem_categoria_google_trends(self, nicho_nome):
        """Todos os nichos devem ter categoria_google_trends válida."""
        config = obter_config_nicho(nicho_nome)
        assert config.categoria_google_trends is not None
        assert isinstance(config.categoria_google_trends, int)
        assert 1 <= config.categoria_google_trends <= 100

    @pytest.mark.parametrize("nicho_nome", ["cultura_pop", "tecnologia", "futebol", "financas", "ciencia", "historia"])
    def test_todos_tem_subreddits_sugeridos(self, nicho_nome):
        """Todos os nichos devem ter subreddits_sugeridos (Subfase 8.3)."""
        config = obter_config_nicho(nicho_nome)
        assert config.subreddits_sugeridos is not None
        assert len(config.subreddits_sugeridos) >= 1
        # Validar formato
        for subreddit in config.subreddits_sugeridos:
            assert subreddit.startswith("r/")


class TestPromptsFinancas:
    """Testa prompts específicos do nicho financas."""

    def test_prompt_ideacao_financas_estrutura(self):
        """Prompt de ideação de financas segue estrutura correta."""
        config = obter_config_nicho("financas")
        prompt = config.prompt_ideacao

        assert "Finanças Pessoais" in prompt or "Economia" in prompt
        assert "DIRETRIZES EDITORIAIS" in prompt
        assert "5 ideias" in prompt
        assert "FORMATO DE SAÍDA ESTRITO" in prompt

    def test_prompt_roteiro_adicional_financas(self):
        """Prompt adicional de financas menciona vox_motion."""
        config = obter_config_nicho("financas")
        prompt = config.prompt_roteiro_adicional

        assert "vox_motion" in prompt.lower()
        assert "número" in prompt.lower() or "estatística" in prompt.lower()

    def test_prompt_short_financas_ganchos(self):
        """Prompt de short de financas tem exemplos de ganchos."""
        config = obter_config_nicho("financas")
        prompt = config.prompt_roteiro_short

        assert "gancho" in prompt.lower()
        assert "R$" in prompt or "milhões" in prompt.lower() or "por mês" in prompt.lower()


class TestPromptsCiencia:
    """Testa prompts específicos do nicho ciencia."""

    def test_prompt_ideacao_ciencia_estrutura(self):
        """Prompt de ideação de ciencia segue estrutura correta."""
        config = obter_config_nicho("ciencia")
        prompt = config.prompt_ideacao

        assert "Ciência" in prompt or "Curiosidades Científicas" in prompt
        assert "astronomia" in prompt.lower() or "biologia" in prompt.lower()
        assert "5 ideias" in prompt

    def test_prompt_roteiro_adicional_ciencia(self):
        """Prompt adicional de ciencia menciona estudos e fatos verificáveis."""
        config = obter_config_nicho("ciencia")
        prompt = config.prompt_roteiro_adicional

        assert "estudos" in prompt.lower() or "cientista" in prompt.lower()
        assert "verificáve" in prompt.lower()  # "verificáveis" sem acento

    def test_prompt_short_ciencia_curiosidades(self):
        """Prompt de short de ciencia foca em curiosidades."""
        config = obter_config_nicho("ciencia")
        prompt = config.prompt_roteiro_short

        assert "fato" in prompt.lower() or "descoberta" in prompt.lower()
        assert "surpreendente" in prompt.lower() or "instigante" in prompt.lower()


class TestPromptsHistoria:
    """Testa prompts específicos do nicho historia."""

    def test_prompt_ideacao_historia_estrutura(self):
        """Prompt de ideação de historia segue estrutura correta."""
        config = obter_config_nicho("historia")
        prompt = config.prompt_ideacao

        assert "História" in prompt or "Geopolítica" in prompt
        assert "civilizações" in prompt.lower() or "guerras" in prompt.lower()
        assert "5 ideias" in prompt

    def test_prompt_roteiro_adicional_historia(self):
        """Prompt adicional de historia menciona vox_motion para timelines."""
        config = obter_config_nicho("historia")
        prompt = config.prompt_roteiro_adicional

        assert "vox_motion" in prompt.lower()
        assert "timeline" in prompt.lower() or "mapa" in prompt.lower()

    def test_prompt_short_historia_narrativa(self):
        """Prompt de short de historia foca em narrativa envolvente."""
        config = obter_config_nicho("historia")
        prompt = config.prompt_roteiro_short

        assert "evento" in prompt.lower() or "civilização" in prompt.lower()
        assert "revelação" in prompt.lower()


class TestGPULockIntegracao:
    """Testa integração do gpu_lock com múltiplos nichos."""

    def test_gpu_lock_importavel(self):
        """Módulo gpu_lock pode ser importado."""
        from pipeline.gpu_lock import gpu_task, _gpu_semaphore
        assert gpu_task is not None
        assert _gpu_semaphore is not None

    @pytest.mark.asyncio
    async def test_gpu_lock_contexto_serializa(self):
        """Contexto do gpu_lock serializa execuções."""
        from pipeline.gpu_lock import gpu_task

        # Simular duas tarefas concorrentes
        resultados = []

        async def tarefa(nome, duracao):
            async with gpu_task(nome):
                import asyncio
                await asyncio.sleep(duracao)
                resultados.append(nome)

        # Executar duas tarefas "simultaneamente"
        import asyncio
        await asyncio.gather(
            tarefa("tarefa1", 0.01),
            tarefa("tarefa2", 0.01),
        )

        # Ambas devem ter completado
        assert len(resultados) == 2
        assert "tarefa1" in resultados
        assert "tarefa2" in resultados


class TestNichoInvalido:
    """Testa comportamento com nicho inexistente."""

    def test_obter_config_nicho_inexistente(self):
        """Deve levantar ValueError para nicho inexistente."""
        with pytest.raises(ValueError, match="não configurado"):
            obter_config_nicho("nicho_inexistente")


class TestEnvExampleAtualizado:
    """Testa que .env.example foi atualizado com novos nichos."""

    def test_env_example_lista_nichos(self):
        """Arquivo .env.example deve listar todos os nichos disponíveis."""
        with open(".env.example", "r") as f:
            conteudo = f.read()

        # Deve mencionar todos os 6 nichos
        assert "cultura_pop" in conteudo
        assert "tecnologia" in conteudo
        assert "futebol" in conteudo
        assert "financas" in conteudo
        assert "ciencia" in conteudo
        assert "historia" in conteudo

        # Deve ter comentário explicativo
        assert "Nichos disponíveis" in conteudo or "nichos" in conteudo.lower()
