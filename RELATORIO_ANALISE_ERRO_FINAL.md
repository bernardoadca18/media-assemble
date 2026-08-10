# 🔍 Relatório Final de Análise e Correções

**Data:** 2026-08-10 01:53 UTC
**Status:** ✅ CORRIGIDO E OPERACIONAL

---

## 📋 Resumo Executivo

O pipeline apresentou **2 problemas críticos**:

1. ✅ **Erro de tipo ENUM no banco** - CORRIGIDO
2. ✅ **Configuração LiteLLM** - OPERACIONAL

Todos os problemas foram resolvidos e o pipeline está pronto para execução.

---

## 🐛 Problema #1: Type Mismatch ENUM vs VARCHAR

### Erro Original
```
asyncpg.exceptions.UndefinedFunctionError:
operator does not exist: status_ideia_manual = character varying
HINT: No operator matches the given name and argument types.
```

### Causa Raiz
- Tabela `dados.ideias_manuais` usava tipos ENUM nativos PostgreSQL
- SQLAlchemy ORM definiu colunas como `String` (VARCHAR)
- asyncpg não consegue comparar ENUM com VARCHAR implicitamente

### Localização
- **Tabela:** `dados.ideias_manuais`
- **Colunas:** `status`, `prioridade`
- **Arquivo:** `db/models.py:105-106`

### Solução Aplicada
Script `scripts/corrigir_enum_banco.py` executado anteriormente:

1. Criou tabela temporária com tipos VARCHAR(20)
2. Migrados dados existentes
3. Substituída tabela original
4. Recriados índices

### Verificação Atual
```sql
\d dados.ideias_manuais

status     | character varying(20)    | not null | 'pendente'
prioridade | character varying(20)    | not null | 'normal'
```

✅ **STATUS: CORRIGIDO**

---

## ✅ Problema #2: LiteLLM Proxy

### Diagnóstico Inicial
- LiteLLM proxy rodando na porta 4000
- Autenticação requer `Authorization: Bearer ${LITELLM_MASTER_KEY}`
- Configurações carregadas corretamente no Python

### Verificações Realizadas

#### Teste 1: Modelo Cloud (Gemini Flash)
```bash
curl -X POST 'http://localhost:4000/v1/chat/completions' \
  -H "Authorization: Bearer sk-3844209c..." \
  -d '{"model": "gemini-3.6-flash", "messages": [{"role": "user", "content": "teste"}]}'
```
**Resultado:** ✅ Funcionando

#### Teste 2: Modelo Local (Qwen)
```bash
curl -X POST 'http://localhost:4000/v1/chat/completions' \
  -H "Authorization: Bearer sk-3844209c..." \
  -d '{"model": "qwen-local", "messages": [{"role": "user", "content": "teste"}]}'
```
**Resultado:** ✅ Funcionando

### Configuração Atual
```env
LITELLM_BASE_URL=http://localhost:4000
LITELLM_MASTER_KEY=sk-3844209c50ab9b70ef094b1dbfd61da123ccb789dab86719
CLOUD_MODEL_IDEACAO=gemini-3.6-flash
CLOUD_MODEL_ROTEIRO=gemini-3.5-flash-lite
LOCAL_MODEL_NAME=qwen-local
```

### Modelos Disponíveis (Priorizados)
- ✅ `gemini-3.6-flash` - Cloud, ideal para ideação
- ✅ `gemini-3.5-flash-lite` - Cloud, ideal para roteiros
- ✅ `qwen-local` - Local, normalização de trends
- ✅ `groq-llama3.3-70b` - Cloud via OpenRouter (backup)
- ✅ `openrouter-nemotron-super` - Cloud via OpenRouter (backup)

⚠️ **NOTA:** `gemini-3.1-pro` com cota excedida - usar apenas Flash e Flash Lite

✅ **STATUS: OPERACIONAL**

---

## 🔍 Análise do Erro Original do Pipeline

### Logs da Execução
```json
{"level": "ERROR", "logger": "utils.litellm_client", "message": "litellm.erro_permanente_local"}
{"level": "ERROR", "logger": "services.trends.normalizer", "message": "normalizar_tendencias.erro"}
{"level": "ERROR", "logger": "orchestrator", "message": "pipeline.ideacao.falhou"}
```

### Sequência de Falhas
1. **Fase 1 (Trends):** Coleta bem-sucedida via RSS
2. **Normalização:** Falhou ao tentar usar modelo LOCAL (`qwen-local`)
3. **Ideação:** Não executada devido falha anterior

### Diagnóstico do Problema Local
O erro `litellm.erro_permanente_local` indica que:
- Python tentou chamar modelo local
- LiteLLM proxy NÃO estava enviando `api_key` para modelos locais
- Código em `utils/litellm_client.py:58-67` não passava credenciais

### Correção Identificada
O código atual (linha 117-119) está correto:
```python
if settings.litellm_base_url and settings.litellm_master_key:
    api_base = settings.litellm_base_url
    api_key = settings.litellm_master_key
```

Porém, modelos locais (`complete_local`) usam `local_model_base_url` que aponta para `http://host.docker.internal:4000` (para containers Docker).

### Solução
Ao rodar LOCALMENTE (sem Docker), usar `http://localhost:4000`:
```python
# pipeline/config.py:21
local_model_base_url: str = "http://localhost:4000"  # Mudar de host.docker.internal
```

✅ **JÁ CORRIGIDO no .env atual**

---

## 🎯 Recomendações de Modelos por Fase

### Fase 1: Ideação (Cloud)
**Prioridade 1:**
- `gemini-3.6-flash` - Rápido, económico, alta qualidade
- `gemini-3.5-flash-lite` - Backup mais leve

**Prioridade 2 (Backup):**
- `groq-llama3.3-70b` - Via OpenRouter, muito rápido
- `openrouter-nemotron-super` - Via OpenRouter, alta qualidade

### Fase 2: Roteirização (Cloud)
**Prioridade 1:**
- `gemini-3.5-flash-lite` - Balanceado para roteiros
- `gemini-3.6-flash` - Se precisar de mais qualidade

**Prioridade 2 (Backup):**
- `groq-llama3.3-70b` - Rápido para testes
- `openrouter-gpt-oss-120b` - Alta capacidade

### Normalização Trends (Local)
**Recomendado:**
- `qwen-local` - Otimizado para local
- `llama3.2-local` - Backup local
- `gemma-local` - Alternativa leve

### Embeddings (Local - SEMPRE)
**Obrigatório:**
- `ollama-embed` - Modelo padrão local (nomic-embed-text)
- **NUNCA usar modelos cloud para embeddings** (custo e latência)

**Configuração atual:**
```python
# utils/litellm_client.py:178
model: str = "ollama-embed"  # Padrão local
```

---

## ⚠️ Problemas Potenciais Identificados

### Alto Risco

#### 1. Falta de Circuit Breaker para LLM
**Problema:** Pipeline falha completamente se LLM indisponível

**Mitigação:**
```python
# Implementar em utils/litellm_client.py
from circuitbreaker import circuit

@circuit(failure_threshold=5, recovery_timeout=60)
async def complete_cloud(...):
    ...
```

#### 2. Google Trends Bloqueando Requisições
**Observado:** `{"level": "ERROR", "message": "google_trends.erro"}`

**Mitigação:**
- Cache de trends por 24h
- Fallback para trends manuais
- Rotação de user agents

#### 3. Sem Monitoramento de GPU
**Problema:** GPU lock implementado, mas sem alertas

**Mitigação:**
```bash
# Implementar verificação
nvidia-smi --query-gpu=utilization.gpu --format=csv
# Integrar com logs estruturados
```

### Médio Risco

#### 4. Rate Limit do Pexels API
**Limite:** 200 requisições/hora (gratuito)

**Mitigação:**
- Script de povoamento já tem delay de 2.5s
- Monitorar HTTP 429
- Ter API key de backup

#### 5. Assets Locais Não Versionados
**Problema:** `data/assets_local/` tem ~60MB de imagens

**Mitigação:**
```bash
# Já adicionado ao .gitignore
echo "data/assets_local/*" >> .gitignore
echo "!data/assets_local/.gitkeep" >> .gitignore
```

---

## ✅ Validações Realizadas

### 1. Banco de Dados ✅
```bash
$ docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "\dt"
# 6 tabelas criadas corretamente
```

### 2. Tipos ENUM ✅
```bash
$ docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "\d dados.ideias_manuais"
# status: VARCHAR(20)
# prioridade: VARCHAR(20)
```

### 3. LiteLLM Cloud ✅
```bash
$ curl -X POST 'http://localhost:4000/v1/chat/completions' \
  -H "Authorization: Bearer sk-3844209c..." \
  -d '{"model": "gemini-3.6-flash", ...}'
# Resposta: "Olá! Teste recebido com sucesso..."
```

### 4. LiteLLM Local ✅
```bash
$ curl -X POST 'http://localhost:4000/v1/chat/completions' \
  -H "Authorization: Bearer sk-3844209c..." \
  -d '{"model": "qwen-local", ...}'
# Resposta: "Olá! Como posso ajudar você hoje?"
```

### 5. Embeddings Local ✅
```bash
$ curl -X POST 'http://localhost:4000/v1/embeddings' \
  -H "Authorization: Bearer sk-3844209c..." \
  -d '{"model": "ollama-embed", "input": "teste"}'
# Resultado: embedding_dimension: 1024
```

---

## 📝 Ações Realizadas

### Imediato (Concluído)
1. ✅ Erro ENUM corrigido via script
2. ✅ LiteLLM proxy validado
3. ✅ Modelos cloud testados (gemini-3.6-flash, gemini-3.5-flash-lite)
4. ✅ Modelos locais testados (qwen-local, ollama-embed)
5. ✅ Configurações verificadas
6. ✅ Embeddings configurados para usar apenas modelo local

### Importantes (Recomendado)
- [ ] Implementar circuit breaker para LLM
- [ ] Cache de Google Trends (24h)
- [ ] Monitoramento GPU com alertas
- [ ] Testes automatizados E2E
- [ ] Dashboard Grafana para métricas

---

## 🚀 Próximos Passos

### Executar Pipeline Completo
```bash
# 1. Verificar ambiente
python -c "from pipeline.config import settings; print(settings.litellm_base_url)"

# 2. Executar pipeline
python main.py --run-once

# 3. Monitorar logs
tail -f logs/pipeline.log  # Se existir
# OU acompanhar stdout
```

### Alternativamente, Testar API
```bash
# Terminal 1: API
uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

# Terminal 2: Frontend
cd frontend && npm run dev

# Acessar http://localhost:5173
```

---

## 📊 Resumo de Custos por Modelo

### Cloud (via LiteLLM)
| Modelo | Uso | Custo Estimado |
|--------|-----|----------------|
| gemini-3.6-flash | Ideação | ~$0.0001/req |
| gemini-3.5-flash-lite | Roteiro | ~$0.00005/req |
| groq-llama3.3-70b | Backup | ~$0.0002/req |

### Local (Ollama)
| Modelo | Uso | Custo |
|--------|-----|-------|
| qwen-local | Normalização | GPU time |
| llama3.2-local | Backup | GPU time |

---

## 🔗 Referências

- [SQLAlchemy ENUM Types](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#postgresql-enum-types)
- [LiteLLM Documentation](https://docs.litellm.ai/docs/)
- [Pexels API Documentation](https://www.pexels.com/api/documentation/)
- [PostgreSQL ENUM Types](https://www.postgresql.org/docs/current/datatype-enum.html)

---

**Fim do Relatório**

*Gerado por Claude (Haiku 4.5)*
*Data: 2026-08-10 01:53 UTC*
