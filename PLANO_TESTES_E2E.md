# 🎬 Plano de Testes End-to-End - Faceless Pipeline

## Visão Geral

Este guia testa **todos os fluxos** do pipeline, desde a configuração até a geração do vídeo final.

**Tempo estimado:** 2-3 horas
**Complexidade:** Moderada (várias integrações)

---

## 📋 Checklist de Pré-requisitos

### 1. Ambiente Python
```bash
# Ativar ambiente virtual
source .venv/bin/activate

# Verificar dependências
pip list | grep -E "fastapi|uvicorn|sqlalchemy|alembic|litellm"
```

### 2. Banco de Dados PostgreSQL
```bash
# Verificar se está rodando
docker ps | grep faceless_postgres

# Se não estiver, iniciar:
docker compose up -d postgres

# Aguardar healthcheck
docker compose logs postgres | grep "ready to accept connections"
```

### 3. Migrações do Banco
```bash
# Executar migrações Alembic
alembic upgrade head

# Verificar tabelas criadas
docker exec -it faceless_postgres psql -U faceless -d faceless_pipeline -c "\dt"
```

### 4. LiteLLM Proxy (Modelos de Linguagem)
```bash
# Verificar se o proxy está rodando
curl -s http://localhost:4000/v1/models | jq .

# Deve retornar lista de modelos disponíveis:
# - qwen-local (local)
# - gemini-3.6-flash (cloud - ideação)
# - gemini-3.1-pro (cloud - roteiro)
```

### 5. Node.js/Remotion (Renderização)
```bash
# Instalar dependências do Remotion
cd remotion && npm install && cd ..

# Verificar instalação
ls -la remotion/node_modules/@remotion
```

---

## 🧪 TESTE 1: Pipeline Completo (Fluxo Principal)

### Objetivo
Executar o pipeline do início ao fim para um nicho específico.

### Passos

#### 1.1. Verificar Assets Locais
```bash
# Verificar se há assets visuais indexados
ls -la data/assets_local/

# Se vazio, criar estrutura de exemplo:
mkdir -p data/assets_local/cultura_pop
# Adicionar algumas imagens/vídeos de teste
```

#### 1.2. Verificar Áudio de Referência
```bash
# Verificar arquivo de voz para TTS
ls -la data/voz_referencia/audio_ref.wav

# Se não existir, criar placeholder ou usar um áudio válido
```

#### 1.3. Executar Pipeline Uma Vez
```bash
# Execução única (modo teste)
python main.py --run-once

# Monitorar logs em tempo real:
tail -f logs/pipeline.log
```

#### 1.4. Verificar Resultado
```bash
# Verificar execuções no banco
docker exec -it faceless_postgres psql -U faceless -d faceless_pipeline \
  -c "SELECT video_id, nicho, etapa_atual, sucesso, caminho_video_final FROM dados.execucoes_pipeline ORDER BY criado_em DESC LIMIT 5;"

# Verificar vídeo gerado (se sucesso=True)
ls -la remotion/videos/output/
```

### ✅ Critérios de Sucesso
- [ ] Pipeline executou sem erros fatais
- [ ] Registro criado na tabela `execucoes_pipeline`
- [ ] `sucesso=True` no registro
- [ ] Arquivo de vídeo gerado em `remotion/videos/output/`

---

## 🧪 TESTE 2: Tratamento de Falhas

### Objetivo
Testar mecanismos de retomada e recuperação de erros.

### Passos

#### 2.1. Simular Falha
```bash
# Desligar LiteLLM durante execução para simular falha
docker compose stop litellm  # se existir

# Ou interromper manualmente:
pkill -f "python main.py"
```

#### 2.2. Listar Execuções Falhas
```bash
python main.py --listar-falhas

# Saída esperada:
# VIDEO_ID                                NICHO               ETAPA               CRIADO_EM
# ----------------------------------------------------------------------------------------------------
# abc123...                               cultura_pop         roteirizacao        2026-08-09 18:00:00
```

#### 2.3. Retomar Execução
```bash
# Retomar do ponto de falha
python main.py --retomar <VIDEO_ID>

# Verificar logs
tail -f logs/pipeline.log
```

### ✅ Critérios de Sucesso
- [ ] Falha detectada e registrada
- [ ] `--listar-falhas` mostra execução interrompida
- [ ] `--retomar` continua do ponto correto
- [ ] Execução completa após retomada

---

## 🧪 TESTE 3: Revisão Manual de Roteiros

### Objetivo
Testar fluxo de aprovação/rejeição manual de roteiros.

### Passos

#### 3.1. Criar Ideia Manual
```bash
# Sugerir uma ideia manualmente
python main.py --sugerir-ideia --nicho cultura_pop --titulo "Top 10 curiosidades sobre Doctor Doom"

# Saída esperada:
# ✅ Ideia salva com ID: 123
```

#### 3.2. Listar Pendentes
```bash
python main.py --listar-pendentes

# Saída esperada:
# VIDEO_ID                                TÍTULO                                           STATUS
# ----------------------------------------------------------------------------------------------------
# abc123...                               Top 10 curiosidades sobre Doctor Doom            pendente
```

#### 3.3. Aprovar/Rejeitar
```bash
# Aprovar roteiro
python main.py --revisar <VIDEO_ID> --aprovar

# OU rejeitar
python main.py --revisar <VIDEO_ID> --rejeitar
```

### ✅ Critérios de Sucesso
- [ ] Ideia salva no banco
- [ ] `--listar-pendentes` mostra corretamente
- [ ] Status atualizado após revisão
- [ ] Pipeline pode usar ideia aprovada

---

## 🧪 TESTE 4: API Backend (FastAPI)

### Objetivo
Testar endpoints da API REST.

### Passos

#### 4.1. Iniciar API
```bash
# Terminal 1: Iniciar servidor
uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

# Terminal 2: Testar endpoints
```

#### 4.2. Testar Endpoints

```bash
# Health check
curl http://localhost:8080/health

# Listar execuções
curl http://localhost:8080/api/execucoes | jq .

# Status do sistema
curl http://localhost:8080/api/status | jq .

# Listar nichos
curl http://localhost:8080/api/nichos | jq .

# Criar ideia manual
curl -X POST http://localhost:8080/api/ideias-manuais \
  -H "Content-Type: application/json" \
  -d '{"nicho": "cultura_pop", "titulo_sugerido": "Teste via API"}' | jq .
```

#### 4.3. Testar via Swagger UI
```bash
# Abrir no navegador:
# http://localhost:8080/docs
```

### ✅ Critérios de Sucesso
- [ ] API responde em `http://localhost:8080`
- [ ] Swagger UI acessível em `/docs`
- [ ] Todos endpoints retornam JSON válido
- [ ] CORS configurado corretamente

---

## 🧪 TESTE 5: Frontend Web

### Objetivo
Testar interface de gestão via navegador.

### Passos

#### 5.1. Iniciar Frontend
```bash
# Terminal 1: API (se não estiver rodando)
uvicorn api.main:app --host 127.0.0.1 --port 8080

# Terminal 2: Frontend
cd frontend && npm run dev
```

#### 5.2. Acessar Páginas

Navegue para `http://localhost:5173` e teste cada página:

| Página | URL | O que testar |
|--------|-----|--------------|
| Dashboard | `/` | Status GPU, estatísticas, execuções recentes |
| Execuções | `/execucoes` | Listar, filtrar, retomar falhas |
| Revisão Manual | `/revisao` | Aprovar/rejeitar roteiros |
| Ideias Manuais | `/ideias-manuais` | Criar e listar ideias |
| Gameplay | `/gameplay` | Segmentos indexados |
| Nichos | `/nichos` | Configurações de nichos |

#### 5.3. Testes Específicos

**Dashboard:**
- [ ] Status da GPU aparece
- [ ] Gráficos de estatísticas renderizam
- [ ] Lista de execuções recentes carrega

**Execuções:**
- [ ] Filtros funcionam (por nicho, status, período)
- [ ] Botão "Retomar" aparece para falhas
- [ ] Detalhes da execução expandem corretamente

**Revisão Manual:**
- [ ] Lista de pendentes carrega
- [ ] Botões Aprovar/Rejeitar funcionam
- [ ] Status atualiza após ação

**Ideias Manuais:**
- [ ] Formulário de criação funciona
- [ ] Lista de ideias carrega
- [ ] Filtro por nicho funciona

### ✅ Critérios de Sucesso
- [ ] Frontend carrega sem erros no console
- [ ] Todas as páginas acessíveis
- [ ] Dados carregam da API
- [ ] Interações funcionam (filtros, botões)

---

## 🧪 TESTE 6: Ingestão de Gameplay

### Objetivo
Testar indexação de vídeos de gameplay para uso como assets.

### Passos

#### 6.1. Preparar Arquivo de Gameplay
```bash
# Verificar estrutura
ls -la data/gameplay/

# Ter um vídeo de gameplay de teste disponível
# Exemplo: data/gameplay/zelda_gameplay.mp4
```

#### 6.2. Ingerir Gameplay
```bash
# Ingerir arquivo único
python main.py --ingerir-gameplay --jogo "Zelda" --arquivo data/gameplay/zelda_gameplay.mp4

# OU ingerir diretório inteiro
python main.py --ingerir-gameplay --jogo "Zelda" --diretorio data/gameplay/zelda_clips/
```

#### 6.3. Listar Segmentos
```bash
# Listar todos
python main.py --listar-gameplay

# Filtrar por jogo
python main.py --listar-gameplay --jogo "Zelda"

# Filtrar por intensidade
python main.py --listar-gameplay --intensidade intenso
```

#### 6.4. Verificar no Banco
```bash
docker exec -it faceless_postgres psql -U faceless -d faceless_pipeline \
  -c "SELECT id, jogo_origem, faixa_intensidade, score_movimento, duracao_segundos FROM dados.gameplay_segmentos LIMIT 10;"
```

### ✅ Critérios de Sucesso
- [ ] Gameplay processado sem erros
- [ ] Segmentos criados no banco
- [ ] Scores de movimento calculados
- [ ] Faixas de intensidade atribuídas

---

## 🧪 TESTE 7: Assets Visuais (Banco Local + Pexels)

### Objetivo
Testar resolução de assets visuais.

### Passos

#### 7.1. Preparar Banco Local
```bash
# Criar estrutura de tags
mkdir -p data/assets_local/doctor_doom
mkdir -p data/assets_local/marvel

# Adicionar imagens de teste
# (adicionar arquivos .jpg/.png/.mp4 nas pastas)
```

#### 7.2. Verificar Integração com Pexels
```bash
# Testar API do Pexels
curl -H "Authorization: $PEXELS_API_KEY" \
  "https://api.pexels.com/v1/search?query=doctor%20doom&per_page=1"
```

#### 7.3. Executar Pipeline e Verificar Logs
```bash
python main.py --run-once

# Verificar logs de resolução de assets
grep "Assets resolvidos" logs/pipeline.log
grep "fallback Pexels" logs/pipeline.log
```

### ✅ Critérios de Sucesso
- [ ] Assets locais indexados por tag
- [ ] Fallback para Pexels funciona quando tag não existe
- [ ] Assets únicos escolhidos aleatoriamente
- [ ] URLs de assets preenchidas no roteiro

---

## 🧪 TESTE 8: Docker Compose (Ambiente Completo)

### Objetivo
Testar toda a stack via Docker.

### Passos

#### 8.1. Build das Imagens
```bash
# Build de todos os serviços
docker compose build
```

#### 8.2. Iniciar Stack Completa
```bash
# Iniciar todos os serviços
docker compose up -d

# Verificar status
docker compose ps

# Saída esperada:
# NAME                  STATUS    PORTS
# faceless_postgres     running   0.0.0.0:5433->5432/tcp
# faceless_api          running   127.0.0.1:8080->8080/tcp
# faceless_frontend     running   0.0.0.0:5173->5173/tcp
# faceless_pipeline     running   (sem porta externa)
```

#### 8.3. Verificar Logs
```bash
# Logs da API
docker compose logs -f api

# Logs do pipeline
docker compose logs -f pipeline

# Logs do frontend
docker compose logs -f frontend
```

#### 8.4. Testar Integração
```bash
# API via Docker
curl http://localhost:8080/health

# Frontend via Docker
curl http://localhost:5173

# Banco via Docker
docker exec -it faceless_postgres psql -U faceless -d faceless_pipeline -c "SELECT 1;"
```

### ✅ Critérios de Sucesso
- [ ] Todos containers rodando
- [ ] Healthchecks passando
- [ ] API acessível na porta 8080
- [ ] Frontend acessível na porta 5173
- [ ] Pipeline executando em background

---

## 🧪 TESTE 9: Metadata Generator

### Objetivo
Testar geração de metadata para upload no YouTube.

### Passos

```bash
# Gerar metadata para um vídeo específico
python main.py --metadata <VIDEO_ID>

# Verificar arquivo gerado
ls -la data/metadata/

# Conteúdo esperado:
# - título
# - descrição
# - tags
# - categoria
# - thumbnail (sugestão)
```

### ✅ Critérios de Sucesso
- [ ] Arquivo JSON gerado
- [ ] Campos obrigatórios preenchidos
- [ ] Tags relevantes geradas
- [ ] Descrição formatada corretamente

---

## 🧪 TESTE 10: Custos de LLM

### Objetivo
Verificar tracking de custos das chamadas de LLM.

### Passos

```bash
# Executar pipeline algumas vezes
python main.py --run-once
python main.py --run-once
python main.py --run-once

# Ver relatório de custos
python main.py --custos

# Saída esperada:
# ============================================================
# RELATÓRIO DE CUSTOS - período
# ============================================================
#
# Total de chamadas: 15
# Total de tokens: 125,000
# Custo total: $0.3421 USD
#
# ────────────────────────────────────────────────────────────
# POR OPERAÇÃO:
# Operação                 Chamadas       Tokens       Custo
# ────────────────────────────────────────────────────────────
# ideacao                        5       25,000     $0.0500
# roteirizacao                   5       75,000     $0.2000
# ...
```

### ✅ Critérios de Sucesso
- [ ] Relatório gera sem erros
- [ ] Contadores de chamadas corretos
- [ ] Tokens somados corretamente
- [ ] Valores em USD calculados

---

## 🔍 Troubleshooting Comum

### Erro: "Connection refused" ao conectar no banco
```bash
# Verificar se container está rodando
docker ps | grep postgres

# Reiniciar container
docker compose restart postgres

# Verificar logs
docker compose logs postgres
```

### Erro: "LiteLLM not responding"
```bash
# Verificar se proxy está rodando
curl http://localhost:4000/v1/models

# Se não estiver, iniciar LiteLLM (fora do escopo deste projeto)
# Verificar documentação do LiteLLM
```

### Erro: "CUDA out of memory"
```bash
# Verificar uso da GPU
nvidia-smi

# Reduzir batch size ou modelo
# No .env:
WHISPER_MODEL_SIZE=small  # ao invés de medium
```

### Erro: "Remotion render failed"
```bash
# Verificar dependências do Remotion
cd remotion && npm install

# Verificar se ffmpeg está instalado
ffmpeg -version

# Testar render manual
cd remotion && npm run render
```

### Frontend não carrega dados da API
```bash
# Verificar CORS no backend
# Em api/main.py, deve ter:
# allow_origins=["http://localhost:5173", "http://localhost:3000"]

# Verificar URL da API no frontend
# Em frontend/.env:
VITE_API_URL=http://localhost:8080
```

---

## 📊 Relatório Final de Testes

Após executar todos os testes, preencher:

```markdown
## Resumo de Testes E2E

**Data:** ____/____/2026
**Executor:** _______________

| Teste | Status | Observações |
|-------|--------|-------------|
| 1. Pipeline Completo | ⬜ PASS / FAIL | |
| 2. Tratamento de Falhas | ⬜ PASS / FAIL | |
| 3. Revisão Manual | ⬜ PASS / FAIL | |
| 4. API Backend | ⬜ PASS / FAIL | |
| 5. Frontend Web | ⬜ PASS / FAIL | |
| 6. Ingestão Gameplay | ⬜ PASS / FAIL | |
| 7. Assets Visuais | ⬜ PASS / FAIL | |
| 8. Docker Compose | ⬜ PASS / FAIL | |
| 9. Metadata Generator | ⬜ PASS / FAIL | |
| 10. Custos LLM | ⬜ PASS / FAIL | |

**Problemas Encontrados:**
-
-
-

**Sugestões de Melhoria:**
-
-
-
```

---

## 🚀 Próximos Passos

Após todos os testes passarem:

1. **Documentar métricas de desempenho**
   - Tempo médio por fase
   - Uso de GPU/memória
   - Custos por vídeo

2. **Configurar monitoramento**
   - Logs estruturados (Grafana Loki)
   - Métricas (Prometheus)
   - Dashboards

3. **Preparar para produção**
   - Backup do banco
   - Estratégia de deploy
   - Escalonamento

4. **Automação**
   - CI/CD pipeline
   - Testes automatizados
   - Deploy automático

---

## 📚 Referências

- [README.md](./README.md) - Documentação principal
- [DEPLOY.md](./DEPLOY.md) - Guia de deploy
- [DOCKER.md](./DOCKER.md) - Documentação Docker
- [guia-pipeline-faceless-python.md](./guia-pipeline-faceless-python.md) - Guia completo
