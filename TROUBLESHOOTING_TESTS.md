# 🔧 Troubleshooting dos Testes E2E

## Status Atual

✅ **Funcionando:**
- Banco PostgreSQL com pgvector
- Ambiente Python com dependências
- 6 tabelas criadas corretamente
- 5 nichos configurados

❌ **Problemas Identificados:**
1. LiteLLM proxy não está rodando (porta 4000)
2. Erro de tipo no enum `status_ideia_manual`

---

## 🚨 Problema 1: LiteLLM Proxy não está rodando

### Diagnóstico
```bash
curl -s http://localhost:4000/v1/models
# Erro: {"error":{"message":"Authentication Error, No api key passed in."}}
```

### Causa
O proxy LiteLLM não está executando na porta 4000. O pipeline depende dele para:
- Geração de ideias (Cloud Model)
- Roteirização (Cloud Model)
- Fallback para modelo local

### Soluções

#### Opção A: Iniciar LiteLLM manualmente (RECOMENDADO)
```bash
# Terminal separado
litellm --config litellm_config.yaml --port 4000

# OU se tiver arquivo de config:
litellm --model_list gpt-4,gemini-pro --port 4000
```

#### Opção B: Configurar credenciais diretas no .env
```bash
# Editar .env e adicionar:
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx
GEMINI_API_KEY=xxx

# E mudar modelos para usar diretamente:
CLOUD_MODEL_IDEACAO=gpt-4o-mini
CLOUD_MODEL_ROTEIRO=gpt-4o
```

#### Opção C: Usar apenas modelo local (LIMITADO)
```bash
# No .env, configurar Ollama local:
LOCAL_MODEL_NAME=llama3
LOCAL_MODEL_BASE_URL=http://localhost:11434

# E comentar/desabilitar cloud models
```

---

## 🚨 Problema 2: Erro de tipo no banco

### Diagnóstico
```
asyncpg.exceptions.UndefinedFunctionError: operator does not exist: status_ideia_manual = character varying
```

### Causa
O SQLAlchemy está passando string `'pendente'` mas o PostgreSQL espera o tipo enum `status_ideia_manual`.

### Solução

#### Correção Imediata (via SQL)
```bash
# Conectar ao banco
docker exec -it faceless_postgres psql -U faceless -d faceless_pipeline

# Executar correção:
ALTER TABLE dados.ideias_manuais 
ALTER COLUMN status TYPE varchar(20) 
USING status::text;

ALTER TABLE dados.ideias_manuais 
ALTER COLUMN prioridade TYPE varchar(20) 
USING prioridade::text;

# Sair
\q
```

#### Verificar correção
```bash
docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "\d dados.ideias_manuais"
```

---

## 📝 Checklist de Pré-requisitos

Antes de executar `python main.py --run-once`, verificar:

### 1. Banco de Dados
```bash
# PostgreSQL rodando?
docker ps | grep faceless_postgres

# Tabelas criadas?
docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "\dt dados.*"

# Nichos configurados?
docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "SELECT nome, ativo FROM dados.nichos;"
```

### 2. LiteLLM Proxy
```bash
# LiteLLM rodando?
curl -s http://localhost:4000/v1/models | jq .

# Deve retornar lista de modelos
```

### 3. Variáveis de Ambiente
```bash
# Verificar .env
cat .env | grep -E "LITELLM|MODEL|API_KEY"

# Mínimo necessário:
# - LITELLM_BASE_URL=http://localhost:4000
# - CLOUD_MODEL_IDEACAO=gemini-3.6-flash
# - CLOUD_MODEL_ROTEIRO=gemini-3.1-pro
```

### 4. Assets e Áudio
```bash
# Assets locais?
ls -la data/assets_local/

# Áudio de referência TTS?
ls -la data/voz_referencia/audio_ref.wav

# Se não existir, criar placeholder:
mkdir -p data/assets_local/cultura_pop
mkdir -p data/voz_referencia
# touch data/voz_referencia/audio_ref.wav
```

---

## 🧪 Teste Simplificado (Sem LLM)

Se quiser testar a estrutura sem LLM:

### 1. Inserir ideia manual diretamente
```bash
docker exec faceless_postgres psql -U faceless -d faceless_pipeline << EOF
INSERT INTO dados.ideias_manuais (nicho, titulo_sugerido, descricao_breve, prioridade, status)
VALUES ('cultura_pop', 'Top 10 Curiosidades sobre Doctor Doom', 'Vídeo sobre o vilão mais icônico do Quarteto Fantástico', 'alta', 'pendente');
EOF
```

### 2. Verificar ideia inserida
```bash
docker exec faceless_postgres psql -U faceless -d faceless_pipeline -c "SELECT * FROM dados.ideias_manuais;"
```

### 3. Testar API (sem pipeline completo)
```bash
# Iniciar API
uvicorn api.main:app --host 127.0.0.1 --port 8080 &

# Health check
curl http://localhost:8080/health

# Listar nichos
curl http://localhost:8080/api/nichos | jq .

# Listar ideias manuais
curl http://localhost:8080/api/ideias-manuais | jq .
```

---

## 🎯 Próximos Passos Recomendados

### Opção 1: Corrigir e testar pipeline completo
1. Iniciar LiteLLM proxy
2. Corrigir tipo enum no banco
3. Executar `python main.py --run-once`

### Opção 2: Testar componentes isoladamente
1. Testar API (independe de LLM)
2. Testar frontend (precisa da API)
3. Testar banco de dados diretamente

### Opção 3: Criar dados de teste
1. Inserir ideias manuais no banco
2. Inserir roteiro de exemplo
3. Testar renderização Remotion

---

## 📞 Comandos Úteis

```bash
# Ver logs do pipeline
tail -f logs/pipeline.log

# Ver logs da API
tail -f logs/api.log

# Verificar GPU
nvidia-smi

# Verificar processos Python
ps aux | grep python

# Matar processos órfãos
pkill -f "python main.py"

# Reiniciar banco do zero
docker compose down -v
docker compose up -d postgres
alembic upgrade head
```

---

## 🔍 Logs Comuns e Significados

### "litellm.erro_permanente_local"
- LiteLLM não está respondendo
- Verificar se proxy está rodando na porta 4000

### "youtube_trending.sem_api_key"
- Aviso: API do YouTube não configurada (não é crítico)

### "google_trends.erro"
- Erro ao acessar Google Trends (pode ser rate limit ou bloqueio)

### "gpu_lock.waiting"
- GPU está sendo usada por outro processo
- Aguardar ou matar processo concorrente

---

## ✅ Validação Rápida

Execute este script para verificar se está pronto:

```bash
#!/bin/bash

echo "=== Verificando ambiente ==="

# Banco
echo -n "PostgreSQL: "
if docker ps | grep -q faceless_postgres; then
    echo "✅ Rodando"
else
    echo "❌ Parado"
fi

# LiteLLM
echo -n "LiteLLM Proxy: "
if curl -s http://localhost:4000/v1/models | jq -e '.data' > /dev/null 2>&1; then
    echo "✅ Respondendo"
else
    echo "❌ Não está rodando"
fi

# Python
echo -n "Python: "
if python --version | grep -q "3.11\|3.13"; then
    echo "✅ Instalado"
else
    echo "⚠️  Verificar versão"
fi

# Tabelas
echo -n "Tabelas banco: "
TABELAS=$(docker exec faceless_postgres psql -U faceless -d faceless_pipeline -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='dados';")
if [ "$TABELAS" -ge 6 ]; then
    echo "✅ $TABELAS tabelas"
else
    echo "❌ Apenas $TABELAS tabelas"
fi

echo ""
echo "=== Status: Pronto para testes? ==="
```
