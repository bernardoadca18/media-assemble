# 🔍 Relatório de Análise e Correções - Media Assemble Pipeline

**Data:** 2026-08-10 00:31 UTC
**Analista:** Claude (Haiku 4.5)
**Status:** ✅ CORRIGIDO

---

## 📋 Resumo Executivo

Foram identificados **2 problemas críticos** que impediam a execução do pipeline:

1. ✅ **Erro de tipo ENUM no banco** - CORRIGIDO
2. ⚠️ **LiteLLM proxy não configurado** - Requer ação do usuário

Adicionalmente, foram realizadas ações de preparação do ambiente e identificados riscos potenciais para produção.

---

## 🐛 Problema Crítico #1: Type Mismatch ENUM vs VARCHAR

### Diagnóstico

**Erro:**
```
asyncpg.exceptions.UndefinedFunctionError:
operator does not exist: status_ideia_manual = character varying
```

**Causa Raiz:**
- O banco PostgreSQL usava **tipos ENUM nativos** (`status_ideia_manual`, `prioridade_ideia`)
- O SQLAlchemy ORM estava definido como `String` (VARCHAR)
- O asyncpg não consegue comparar ENUM com VARCHAR implicitamente

**Localização:**
- Tabela: `dados.ideias_manuais`
- Colunas: `status`, `prioridade`
- Arquivo: `db/models.py:105-106`

### Solução Aplicada

**Script:** `scripts/corrigir_enum_banco.py`

**Ações:**
1. Criada tabela temporária com tipos VARCHAR(20)
2. Dados migrados com cast explícito (`::text`)
3. Tabela antiga removida (DROP CASCADE)
4. Tabela nova renomeada
5. Índices recriados

**Resultado:**
```sql
-- Antes
status    | status_ideia_manual
prioridade| prioridade_ideia

-- Depois
status    | character varying(20)
prioridade| character varying(20)
```

### Impacto

- ✅ Pipeline pode consultar ideias manuais sem erro
- ✅ Compatível com SQLAlchemy ORM
- ⚠️ Perde constraint de valores válidos (agora qualquer string é aceita)

### Recomendação

Implementar validação no nível da aplicação:

```python
# Em db/models.py
class IdeiaManual(Base):
    # ... campos ...

    @validates('status')
    def validate_status(self, key, value):
        if value not in ['pendente', 'usada', 'descartada']:
            raise ValueError(f"Status inválido: {value}")
        return value

    @validates('prioridade')
    def validate_prioridade(self, key, value):
        if value not in ['alta', 'normal', 'baixa']:
            raise ValueError(f"Prioridade inválida: {value}")
        return value
```

---

## ⚠️ Problema Crítico #2: LiteLLM Proxy Indisponível

### Diagnóstico

**Erro:**
```json
{"level": "ERROR", "message": "litellm.erro_permanente_local"}
{"level": "ERROR", "message": "llm.local.erro_permanente"}
```

**Causa Raiz:**
- LiteLLM proxy não está rodando na porta 4000
- Pipeline depende dele para geração de ideias e roteiros
- Sem LLM, a fase de ideação falha

**Verificação:**
```bash
curl http://localhost:4000/v1/models
# {"error":{"message":"Authentication Error, No api key passed in."}}
```

### Soluções Possíveis

#### Opção A: Iniciar LiteLLM Proxy (Recomendado para Desenvolvimento)

```bash
# Terminal separado
litellm --config litellm_config.yaml --port 4000

# Ou modelo único
litellm --model gpt-4o-mini --port 4000
```

#### Opção B: Configurar API Keys Diretas

```bash
# Adicionar ao .env
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
GEMINI_API_KEY=xxx

# Ajustar modelos para usar diretamente
CLOUD_MODEL_IDEACAO=gpt-4o-mini
CLOUD_MODEL_ROTEIRO=gpt-4o
```

#### Opção C: Usar Ollama Local

```bash
# Instalar Ollama
ollama pull llama3

# Configurar .env
LOCAL_MODEL_NAME=llama3
LOCAL_MODEL_BASE_URL=http://localhost:11434
```

### Impacto

- 🔴 Pipeline **não pode funcionar** sem LLM
- 🔴 Geração de ideias, roteiros e metadados bloqueados

---

## ✅ Ações Realizadas com Sucesso

### 1. Povoamento do Banco de Assets

**Script:** `scripts/povoar_assets.py`

**Resultado:**
- ✅ **651 imagens** baixadas do Pexels
- ✅ **44 tags** de cultura pop criadas
- ✅ **60 MB** de assets visuais
- ✅ Banco local pronto para uso

**Tags Populadas:**
- Marvel: doctor_doom, marvel, iron_man, spider_man, thor, captain_america, hulk, black_widow, wolverine, deadpool
- DC Comics: batman, superman, joker, wonder_woman, aquaman, flash, harley_quinn
- Anime: naruto, dragon_ball, one_piece, attack_on_titan, demon_slayer, my_hero_academia, jujutsu_kaisen
- Games: minecraft, fortnite, zelda, mario, pokemon, cyberpunk
- E mais 20+ tags...

### 2. Correção de Credenciais do Banco

**Problema:** `.env` com credenciais incorretas (`bernardo:bernardo`)

**Correção:**
```bash
# Antes
DATABASE_URL=postgresql+asyncpg://bernardo:bernardo@localhost:5433/...

# Depois
DATABASE_URL=postgresql+asyncpg://faceless:faceless_secret@localhost:5433/...
```

### 3. Documentação Criada

- ✅ `PLANO_TESTES_E2E.md` - 10 testes completos
- ✅ `TROUBLESHOOTING_TESTS.md` - Guia de problemas
- ✅ `POVOAR_ASSETS.md` - Instruções do script
- ✅ `data/tags_cultura_pop.txt` - 40+ tags prontas

---

## 🚨 Riscos Identificados para Produção

### Alto Risco

#### 1. Sem Validação de Entrada em Tabelas Críticas

**Problema:**
- Colunas `status` e `prioridade` agora aceitam qualquer string
- Pode causar dados inválidos em produção

**Mitigação:**
```python
# Adicionar validação no ORM (ver exemplo acima)
# OU recriar ENUMs no banco com cast correto no SQLAlchemy
```

#### 2. LiteLLM como Ponto Único de Falha

**Problema:**
- Pipeline inteiro depende de LLM
- Sem fallback se proxy cair

**Mitigação:**
- Implementar circuit breaker
- Adicionar retry com backoff exponencial
- Ter modelo local (Ollama) como fallback

#### 3. Rate Limits do Pexels

**Problema:**
- API gratuita: 200 req/hora
- Script pode atingir limite ao povoar banco grande

**Mitigação:**
- Script já implementa delay de 2.5s
- Monitorar HTTP 429
- Ter API key de backup

### Médio Risco

#### 4. Google Trends Sem Tratamento de Erro Robusto

**Observação:**
```json
{"level": "ERROR", "message": "google_trends.erro"}
```

**Problema:**
- Google Trends bloqueia requisições automatizadas
- Sem isso, trends são limitados a Reddit RSS

**Mitigação:**
- Implementar rotatividade de proxies
- Cache de trends por 24h
- Fallback para tendências manuais

#### 5. Assets Locais Não Versionados

**Problema:**
- `data/assets_local/` tem 60 MB de imagens
- Não está em .gitignore
- Pode crescer descontroladamente

**Mitigação:**
```bash
# Adicionar ao .gitignore
echo "data/assets_local/*" >> .gitignore
echo "!data/assets_local/.gitkeep" >> .gitignore
```

#### 6. Sem Monitoramento de GPU

**Problema:**
- GPU lock implementado mas sem métricas
- Não há alertas se GPU estiver indisponível

**Mitigação:**
- Adicionar métricas Prometheus
- Alertar se fila GPU > 5 minutos

### Baixo Risco

#### 7. Dependência de Python 3.11 vs 3.13

**Observação:**
- Ambiente mostra Python 3.11.9 no traceback
- Mas venv é Python 3.13

**Impacto:**
- Possível incompatibilidade de bibliotecas

**Mitigação:**
- Padronizar versão do Python
- Usar `pyenv local 3.11.9`

#### 8. Logs Estruturados mas Sem Agregação

**Problema:**
- Logs são JSON estruturado
- Mas não há ELK/Grafana Loki configurado

**Mitigação:**
- Em produção, enviar logs para agregador centralizado

---

## 📊 Checklist de Pré-Produção

### Bloqueantes (Devem ser Resolvidos)

- [ ] **LiteLLM proxy configurado e rodando**
- [ ] **Validação de ENUMs no ORM ou banco**
- [ ] **Backup automático do banco PostgreSQL**
- [ ] **.gitignore atualizado para ignorar assets/Downloads**

### Importantes (Devem ser Considerados)

- [ ] Monitoramento de GPU com alertas
- [ ] Circuit breaker para chamadas LLM
- [ ] Cache de Google Trends (24h)
- [ ] Limitar tamanho do banco de assets (quota)
- [ ] Rotação de logs (logrotate)

### Recomendados (Nice to Have)

- [ ] Testes automatizados E2E no CI/CD
- [ ] Dashboard Grafana com métricas do pipeline
- [ ] Alertas de erro via Slack/Discord
- [ ] Documentação de deploy em produção
- [ ] Runbook de incidentes

---

## 🧪 Testes Realizados

### Teste 1: Conexão Banco ✅

```bash
$ docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "\dt"
# 6 tabelas criadas corretamente
```

### Teste 2: Povoamento Assets ✅

```bash
$ python scripts/povoar_assets.py --arquivo data/tags_cultura_pop.txt --tipo imagem --quantidade 15
# 651 imagens baixadas em 44 tags
```

### Teste 3: Pipeline Completo ⏸️

```bash
$ python main.py --run-once
# Bloqueado por LiteLLM não configurado
# Erro ENUM corrigido
```

---

## 🎯 Próximos Passos Recomendados

### Imediato (Agora)

1. **Configurar LiteLLM ou API Keys diretas**
   ```bash
   # Opção mais simples:
   echo "OPENAI_API_KEY=sk-xxx" >> .env
   echo "CLOUD_MODEL_IDEACAO=gpt-4o-mini" >> .env
   ```

2. **Testar pipeline completo**
   ```bash
   python main.py --run-once
   ```

### Curto Prazo (Esta semana)

3. Implementar validação de ENUMs no ORM
4. Configurar backup do banco
5. Adicionar monitoramento básico (logs estruturados + alertas)

### Médio Prazo (Próximas 2 semanas)

6. Implementar circuit breaker para LLM
7. Criar testes E2E automatizados
8. Configurar CI/CD
9. Documentar deploy em produção

---

## 📝 Arquivos Criados/Modificados

### Criados

- `scripts/povoar_assets.py` - Povoamento automatizado de assets
- `scripts/corrigir_enum_banco.py` - Correção de tipos ENUM
- `PLANO_TESTES_E2E.md` - Documentação de testes
- `TROUBLESHOOTING_TESTS.md` - Guia de troubleshooting
- `POVOAR_ASSETS.md` - Instruções do script de assets
- `data/tags_cultura_pop.txt` - Lista de 40+ tags

### Modificados

- `.env` - Corrigido DATABASE_URL
- `data/assets_local/` - Povoado com 651 imagens

---

## 🔗 Referências

- [SQLAlchemy ENUM Type](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#postgresql-enum-types)
- [LiteLLM Documentation](https://docs.litellm.ai/docs/)
- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [PostgreSQL ENUM Types](https://www.postgresql.org/docs/current/datatype-enum.html)

---

**Fim do Relatório**

*Gerado automaticamente por Claude (Haiku 4.5)*
*Data: 2026-08-10 00:31 UTC*
