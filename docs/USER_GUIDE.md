# Faceless Pipeline — Guia Completo do Usuário

> Sistema automatizado de geração de vídeos "faceless" para YouTube usando IA

---

## Sumário

1. [Visão Geral](#visão-geral)
2. [Arquitetura](#arquitetura)
3. [Microsserviços](#microsserviços)
4. [API Endpoints](#api-endpoints)
5. [Configuração Inicial](#configuração-inicial)
6. [Guia de Uso](#guia-de-uso)
7. [Fluxo de Dados](#fluxo-de-dados)
8. [Estrutura de Diretórios](#estrutura-de-diretórios)
9. [Variáveis de Ambiente](#variáveis-de-ambiente)
10. [Nichos Disponíveis](#nichos-disponíveis)
11. [Dicas e Boas Práticas](#dicas-e-boas-práticas)
12. [Troubleshooting](#troubleshooting)

---

## Visão Geral

O **Faceless Pipeline** é um sistema completo para automação de canais "faceless" no YouTube. O pipeline coleta tendências, gera ideias, escreve roteiros, produz áudio com voz sintetizada, busca assets visuais e renderiza vídeos automaticamente.

### Capacidades

- **Coleta automática de tendências** de Google Trends, Reddit, YouTube e RSS
- **Ideação com IA** usando modelos de linguagem (Gemini, Claude, GPT)
- **Roteirização completa** com múltiplas cenas e elementos gráficos
- **Síntese de voz** com clone de voz personalizado (F5-TTS)
- **Validação de qualidade** de áudio via Whisper (WER < 5%)
- **Resolução de assets** com banco local + fallback Pexels
- **Renderização** via Remotion (React-based)
- **Geração de Shorts** automáticos a partir de vídeos longos
- **Suporte a gameplay** com segmentação e crop vertical

### Tecnologias

| Componente | Tecnologia |
|------------|------------|
| Backend | Python 3.11+ (asyncio) |
| Banco de Dados | PostgreSQL 15+ com pgvector |
| LLM Gateway | LiteLLM (multi-provider) |
| TTS | F5-TTS (clone de voz) |
| Transcrição | Faster-Whisper (CUDA) |
| Renderização | Remotion (React/TypeScript) |
| API HTTP | FastAPI |
| Agendamento | APScheduler |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORQUESTRADOR                              │
│                    (pipeline/orchestrator.py)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   FASE 1      │    │   FASE 2      │    │   FASE 3      │
│  Ideação      │───▶│Roteirização   │───▶│    Áudio      │
└───────────────┘    └───────────────┘    └───────────────┘
                                                   │
        ┌──────────────────────────────────────────┘
        │
        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   FASE 4      │    │   FASE 5      │    │   FASE 6      │
│ Assets Visuais│───▶│ Renderização  │───▶│   Metadata    │
└───────────────┘    └───────────────┘    └───────────────┘
```

### Fluxo de Dados

```
Tendências ──▶ Normalização ──▶ Ideação (LLM)
                                        │
                                        ▼
                               Roteiro Completo
                                        │
                        ┌───────────────┼───────────────┐
                        │               │               │
                        ▼               ▼               ▼
                    TTS/Clone     Validação WER   Concatenação
                        │               │               │
                        └───────────────┴───────────────┘
                                        │
                                        ▼
                              Áudio Master (+timestamps)
                                        │
                                        ▼
                            Resolução de Assets (Local + Pexels)
                                        │
                                        ▼
                            Renderização (Remotion)
                                        │
                                        ▼
                               Vídeo Final (.mp4)
                                        │
                                        ▼
                               Metadata de Publicação
```

---

## Microsserviços

### 1. Pipeline (`pipeline/`)

#### `orchestrator.py`
O "maestro" que coordena todas as fases.

**Responsabilidades:**
- Executar pipeline ponta-a-ponta
- Gerenciar estado entre fases
- Tratar falhas e permitir retomada
- Gerar Shorts automaticamente

**Funções principais:**
- `rodar_pipeline_completo(nicho)` — Executa todas as fases
- `retomar_execucao_falha(video_id)` — Retoma de onde parou
- `rodar_etapa_ideacao(nicho)` — Fase 1
- `rodar_etapa_roteirizacao(ideia, nicho)` — Fase 2

#### `config.py`
Configurações centralizadas do projeto.

**Carrega:**
- Variáveis de ambiente (.env)
- Paths de diretórios
- Configurações de áudio, GPU, gameplay

#### `schemas.py`
Schemas Pydantic — "fonte da verdade" estrutural.

**Modelos principais:**
- `Ideia` — Ideia gerada na Fase 1
- `Roteiro` — Roteiro completo com cenas
- `Cena` — Cena individual do roteiro
- `Midia` — Configuração de busca de assets
- `MetadataPublicacao` — Títulos, descrição, tags

#### `nichos.py`
Configurações específicas por nicho.

**Cada nicho define:**
- Prompt de ideação
- Prompt de roteiro adicional
- Fontes de tendências (Google Trends, subreddits)
- Prompt para Shorts
- Preferências de gameplay

#### `gpu_lock.py`
Gerenciamento de acesso exclusivo à GPU.

**Uso:**
```python
async with gpu_task("f5-tts-cena-03"):
    # código que usa GPU
```

---

### 2. Services — Trends (`services/trends/`)

#### `scraper.py`
Coleta tendências de múltiplas fontes.

**Fontes:**
- Google Trends (pytrends)
- Reddit RSS (subreddits configurados)
- YouTube Trending (YouTube Data API v3)
- RSS de nicho (feeds personalizados)
- Google Custom Search

**Função principal:**
```python
async def coletar_tendencias(nicho: str) -> list[str]
```

#### `normalizer.py`
Normaliza e limpa tendências brutas.

**Operações:**
- Remove duplicatas
- Limpa caracteres especiais
- Padroniza formato

#### `rss_sources.py`
Fontes RSS adicionais por nicho.

**Inclui:**
- Feeds de notícias específicos
- Google Custom Search para tópicos

---

### 3. Services — Ideation (`services/ideation/`)

#### `agent.py`
Agente de ideação usando LLM.

**Responsabilidades:**
- Gerar 5 ideias a partir de tendências
- Aplicar prompt específico do nicho
- Evitar duplicatas (RAG)
- Processar ideias manuais do usuário

**Função principal:**
```python
async def gerar_ideias(nicho: str, tendencias: list[str]) -> list[Ideia]
```

#### `rag_client.py`
Consulta histórico de vídeos para evitar repetição.

**Função:**
```python
async def buscar_titulos_recentes(nicho: str, limite: int = 30) -> list[str]
```

---

### 4. Services — Scripting (`services/scripting/`)

#### `writer_agent.py`
Agente de roteirização.

**Responsabilidades:**
- Gerar roteiro completo com 10-15 cenas
- Aplicar estilo visual (ken_burns, vox_motion, gameplay_bg)
- Incluir elementos gráficos (citações, timelines, gráficos)
- Calcular duração e estrutura

**Função principal:**
```python
async def gerar_roteiro(ideia: Ideia, nicho: str) -> Roteiro
```

#### `clip_selector.py`
Seleciona trechos para Shorts.

**Responsabilidades:**
- Identificar melhores trechos do vídeo longo
- Criar ganchos impactantes
- Gerar roteiros derivados

---

### 5. Services — Audio (`services/audio/`)

#### `tts_engine.py`
Motor de síntese de voz (F5-TTS).

**Responsabilidades:**
- Gerar áudio a partir de texto
- Usar voz de referência (clone)
- Suportar seeds para variação

#### `validator.py`
Validação de qualidade via Whisper.

**Responsabilidades:**
- Transcrever áudio gerado
- Calcular WER (Word Error Rate)
- Comparar com texto esperado

**Função principal:**
```python
async def validar_audio(caminho_audio: Path, texto_esperado: str) -> tuple[float, list[Palavra]]
```

#### `mixer.py`
Concatenação de áudios.

**Responsabilidades:**
- Juntar áudios de todas as cenas
- Gerar timeline de palavras (para legendas)
- Criar áudio master

#### `timbre_variation.py`
Variação de timbre por canal (Fase 9.3).

**Responsabilidades:**
- Aplicar pitch shift determinístico por canal
- Ajustar velocidade de fala
- Manter consistência por canal_id

#### `pipeline_audio.py`
Orquestra todo o pipeline de áudio.

**Função principal:**
```python
async def gerar_audio_do_roteiro(roteiro: Roteiro) -> Roteiro
```

---

### 6. Services — Visual (`services/visual/`)

#### `asset_resolver.py`
Resolve assets visuais para cada cena.

**Estratégia:**
1. Buscar no banco local (`data/assets_local/`)
2. Se não encontrar, buscar no Pexels (fallback)
3. Se não encontrar, marcar para revisão manual

**Função principal:**
```python
async def resolver_assets_do_roteiro(roteiro: Roteiro) -> Roteiro
```

#### `fallback_scraper.py`
Busca assets externos (Pexels API).

**Responsabilidades:**
- Buscar imagens/vídeos no Pexels
- Baixar e salvar localmente
- Respeitar rate limits

#### `triagem_llm.py`
Triagem de assets com LLM (opcional).

---

### 7. Services — Gameplay (`services/gameplay/`)

#### `ingestion.py`
Pipeline de ingestão de gameplay.

**Responsabilidades:**
- Segmentar vídeos brutos em clipes de 30s
- Calcular score de movimento
- Classificar intensidade (calmo, moderado, intenso)
- Indexar no banco de dados

**Função principal:**
```python
async def ingerir_arquivo_gameplay(arquivo_path: Path, jogo: str) -> list[str]
```

#### `resolver.py`
Resolve segmentos de gameplay para vídeos.

**Responsabilidades:**
- Selecionar segmentos por intensidade
- Aplicar crossfade entre clipes
- Respeitar janela de reuso (30 dias)

#### `crop_config.py`
Configuração de crop por jogo (Fase 9.4).

**Responsabilidades:**
- Offset Y para cada jogo (evitar HUD)
- Match parcial de nome de jogo
- Defaults centrados

**Jogos configurados:**
- Minecraft, Fortnite, Valorant
- League of Legends, GTA V, Call of Duty
- Apex Legends, Dota 2, CS:GO, Free Fire

---

### 8. Services — Render (`services/render/`)

#### `remotion_bridge.py`
Ponte Python → Remotion CLI.

**Responsabilidades:**
- Serializar roteiro para JSON
- Copiar assets para `remotion/public/`
- Invocar Remotion CLI via subprocess
- Gerenciar timeouts

**Funções principais:**
```python
async def renderizar_video(roteiro: Roteiro) -> Path
async def renderizar_video_short(roteiro: Roteiro) -> Path
```

---

### 9. Services — Metadata Generator (`services/metadata_generator.py`)

Gera metadata de publicação para YouTube.

**Responsabilidades:**
- Sugerir 2-3 títulos otimizados
- Gerar descrição com capítulos
- Criar tags relevantes
- Sugerir playlist

---

### 10. Database (`db/`)

#### `models.py`
Modelos SQLAlchemy.

**Tabelas:**
- `dados.videos_ideias` — Ideias geradas
- `dados.roteiros` — Roteiros completos
- `dados.execucoes_pipeline` — Rastreabilidade
- `dados.ideias_manuais` — Ideias do usuário
- `dados.gameplay_segmentos` — Segmentos indexados

#### `session.py`
Gerenciamento de sessões async.

---

### 11. Utils (`utils/`)

#### `litellm_client.py`
Cliente único para LiteLLM.

**Funções:**
- `complete_local()` — Modelo local (Ollama/vLLM)
- `complete_cloud()` — Modelo em nuvem (Gemini, Claude, GPT)
- `generate_embedding()` — Embeddings para duplicidade

#### `logger.py`
Logging estruturado (structlog).

#### `cost_tracker.py`
Rastreamento de custos de LLM.

#### `retry.py`
Lógica de retry com backoff.

---

## API Endpoints

A aplicação expõe uma API HTTP via FastAPI.

### Base URL
```
http://localhost:8000
```

### Endpoints

#### `GET /health`
Health check para monitoramento.

**Resposta:**
```json
{
  "status": "ok",
  "timestamp": "2024-01-15T10:30:00"
}
```

---

#### `GET /execucoes`
Lista execuções do pipeline com filtros.

**Parâmetros:**
- `nicho` (opcional): Filtrar por nicho
- `status` (opcional): "sucesso" ou "falha"
- `limite` (opcional): Máximo de registros (default: 50)

**Resposta:**
```json
[
  {
    "video_id": "abc123",
    "nicho": "cultura_pop",
    "etapa_atual": "renderizacao",
    "sucesso": true,
    "motivo_falha": null,
    "criado_em": "2024-01-15T10:00:00"
  }
]
```

---

#### `GET /execucoes/{video_id}`
Detalhes de uma execução específica.

**Resposta:**
```json
{
  "video_id": "abc123",
  "nicho": "cultura_pop",
  "etapa_atual": "renderizacao",
  "sucesso": true,
  "caminho_video_final": "data/output_final/abc123.mp4",
  "wer_medio": 0.032,
  "motivo_falha": null,
  "criado_em": "2024-01-15T10:00:00"
}
```

---

#### `GET /execucoes/{video_id}/metadata`
Metadata de publicação do vídeo.

**Resposta:**
```json
{
  "titulos": [
    "Os 7 Segredos Mais Sombrios de Naruto",
    "Naruto: Segredos que Você Não Conhecia"
  ],
  "descricao": "Descrição do vídeo com capítulos...",
  "tags": ["naruto", "anime", "lore"],
  "playlist_sugerida": "Lore de Anime",
  "playlist_nova": false
}
```

---

#### `POST /ideias-manuais`
Cria uma ideia manual.

**Body:**
```json
{
  "nicho": "cultura_pop",
  "titulo_sugerido": "A História Secreta de Dark Souls",
  "descricao_breve": "Explicar a lore oculta de Dark Souls",
  "prioridade": "alta"
}
```

**Resposta:** (201 Created)
```json
{
  "id": 42,
  "nicho": "cultura_pop",
  "titulo_sugerido": "A História Secreta de Dark Souls",
  "status": "pendente",
  "prioridade": "alta",
  "criado_em": "2024-01-15T10:30:00"
}
```

---

#### `GET /ideias-manuais`
Lista ideias manuais.

**Parâmetros:**
- `nicho` (opcional): Filtrar por nicho
- `status` (opcional): "pendente", "usada", "descartada"
- `limite` (opcional): Máximo de registros

---

#### `DELETE /ideias-manuais/{ideia_id}`
Descarta uma ideia manual.

---

## Configuração Inicial

### Pré-requisitos

1. **Sistema Operacional:** Linux (recomendado) ou macOS
2. **Python:** 3.11+
3. **PostgreSQL:** 15+
4. **FFmpeg:** Para processamento de áudio/vídeo
5. **Node.js:** 18+ (para Remotion)
6. **GPU:** NVIDIA com CUDA (opcional, mas recomendado)

### Instalação

#### Opção 1: Docker Compose (Recomendado)

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/faceless-pipeline.git
cd faceless-pipeline

# 2. Copie o arquivo de exemplo
cp .env.example .env

# 3. Configure o .env com suas credenciais
nano .env

# 4. Inicie os serviços
docker-compose up -d

# 5. Verifique logs
docker-compose logs -f pipeline
```

#### Opção 2: Instalação Local

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/faceless-pipeline.git
cd faceless-pipeline

# 2. Crie ambiente virtual
python -m venv .venv
source .venv/bin/activate

# 3. Instale dependências
pip install -r requirements.txt

# 4. Configure PostgreSQL
sudo -u postgres psql -c "CREATE DATABASE faceless_pipeline;"
sudo -u postgres psql -c "CREATE USER faceless WITH PASSWORD 'sua_senha';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE faceless_pipeline TO faceless;"

# 5. Execute migrations
psql -d faceless_pipeline -f db/migrations/versions/001_initial_schema.sql

# 6. Configure o .env
cp .env.example .env
nano .env

# 7. Instale dependências do Remotion
cd remotion && npm install && cd ..

# 8. Execute o pipeline
python main.py --run-once
```

### Configuração do .env

Arquivo `.env` mínimo:

```bash
# Banco de Dados
DATABASE_URL=postgresql+asyncpg://faceless:sua_senha@localhost:5432/faceless_pipeline

# LLM - Modelo de Ideação (nuvem)
CLOUD_MODEL_IDEACAO=gemini/gemini-1.5-flash
GEMINI_API_KEY=sua_chave_aqui

# LLM - Modelo de Roteiro (nuvem)
CLOUD_MODEL_ROTEIRO=anthropic/claude-3-5-sonnet-20240620
ANTHROPIC_API_KEY=sua_chave_aqui

# Modelo Local (opcional, para normalização)
LOCAL_MODEL_NAME=ollama/qwen2.5:7b
LOCAL_MODEL_BASE_URL=http://localhost:11434

# Áudio/GPU
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
F5_TTS_REF_AUDIO=data/voz_referencia/minha_voz.wav

# Pipeline
NICHOS_ATIVOS=cultura_pop

# Assets Externos
PEXELS_API_KEY=sua_chave_pexels

# YouTube Data API (opcional)
YOUTUBE_API_KEY=sua_chave_youtube
```

### Preparar Diretórios de Dados

```bash
# Criar estrutura de diretórios
mkdir -p data/{voz_referencia,assets_local,gameplay_raw,gameplay_processed,output_final}

# Adicionar voz de referência (30-60 segundos de áudio limpo)
cp minha_voz.wav data/voz_referencia/

# Adicionar assets locais (opcional)
mkdir -p data/assets_local/naruto
cp imagem_naruto.jpg data/assets_local/naruto/
```

---

## Guia de Uso

### Execução Básica

```bash
# Executar uma vez (um vídeo para cada nicho ativo)
python main.py --run-once

# Executar em modo agendado (scheduler)
python main.py

# Executar para nicho específico
python main.py --run-once --nicho cultura_pop
```

### Retomar Execuções Falhas

```bash
# Listar execuções falhas
python main.py --listar-falhas

# Retomar execução específica
python main.py --retomar VIDEO_ID
```

### Revisão Manual de Roteiros

```bash
# Listar roteiros pendentes
python main.py --listar-pendentes

# Aprovar roteiro
python main.py --revisar VIDEO_ID --aprovar

# Rejeitar roteiro
python main.py --revisar VIDEO_ID --rejeitar
```

### Ideias Manuais

```bash
# Sugerir ideia manual
python main.py --sugerir-ideia --nicho cultura_pop --titulo "Minha Ideia" --prioridade alta

# Listar ideias manuais
python main.py --listar-ideias-manuais

# Descartar ideia
python main.py --descartar-ideia ID
```

### Gameplay

```bash
# Ingerir arquivo de gameplay
python main.py --ingerir-gameplay --jogo minecraft --arquivo gameplay.mp4

# Ingerir diretório de gameplay
python main.py --ingerir-gameplay --jogo fortnite --diretorio /path/to/gameplay/

# Listar segmentos
python main.py --listar-gameplay --jogo minecraft --intensidade moderado
```

### Relatórios

```bash
# Relatório de custos do mês
python main.py --custos
```

### Metadata de Publicação

```bash
# Gerar metadata para vídeo
python main.py --metadata VIDEO_ID
```

---

## Estrutura de Diretórios

```
faceless-pipeline/
├── api/                    # API HTTP (FastAPI)
│   └── status.py
├── data/                   # Dados locais
│   ├── assets_local/       # Banco de assets (organizado por tags)
│   ├── gameplay_raw/       # Gameplay bruta para ingestão
│   ├── gameplay_processed/ # Segmentos processados
│   ├── output_final/       # Vídeos renderizados
│   └── voz_referencia/     # Voz de referência para TTS
├── db/                     # Banco de dados
│   ├── migrations/         # Migrations SQL
│   ├── models.py           # Modelos SQLAlchemy
│   └── session.py
├── docs/                   # Documentação
├── logs/                   # Logs do sistema
├── pipeline/               # Orquestração
│   ├── config.py
│   ├── gpu_lock.py
│   ├── nichos.py
│   ├── orchestrator.py
│   └── schemas.py
├── remotion/               # Renderização (React/TypeScript)
│   ├── src/
│   ├── public/             # Assets para renderização
│   └── package.json
├── services/               # Microsserviços
│   ├── audio/
│   ├── gameplay/
│   ├── ideation/
│   ├── metadata_generator.py
│   ├── render/
│   ├── scripting/
│   ├── trends/
│   └── visual/
├── tests/                  # Testes automatizados
├── utils/                  # Utilitários
├── main.py                 # Entry point
├── requirements.txt        # Dependências Python
├── docker-compose.yml
└── .env                    # Configurações (não commitar)
```

---

## Variáveis de Ambiente

### Banco de Dados
| Variável | Descrição | Default |
|----------|-----------|---------|
| `DATABASE_URL` | URL de conexão PostgreSQL | Obrigatório |

### LiteLLM / Modelos
| Variável | Descrição | Default |
|----------|-----------|---------|
| `LITELLM_PROXY_URL` | URL do proxy LiteLLM (opcional) | - |
| `LOCAL_MODEL_NAME` | Modelo local via Ollama/vLLM | `ollama/qwen2.5:7b` |
| `LOCAL_MODEL_BASE_URL` | URL do Ollama/vLLM | `http://localhost:11434` |
| `CLOUD_MODEL_IDEACAO` | Modelo para ideação | `gemini/gemini-1.5-flash` |
| `CLOUD_MODEL_ROTEIRO` | Modelo para roteiro | `anthropic/claude-3-5-sonnet` |

### API Keys
| Variável | Descrição |
|----------|-----------|
| `GEMINI_API_KEY` | Chave do Google Gemini |
| `OPENAI_API_KEY` | Chave do OpenAI |
| `ANTHROPIC_API_KEY` | Chave do Anthropic |
| `PEXELS_API_KEY` | Chave do Pexels (assets) |
| `YOUTUBE_API_KEY` | Chave do YouTube Data API |

### Áudio / GPU
| Variável | Descrição | Default |
|----------|-----------|---------|
| `WHISPER_MODEL_SIZE` | Tamanho do modelo Whisper | `medium` |
| `WHISPER_DEVICE` | Dispositivo (cuda/cpu) | `cuda` |
| `WHISPER_COMPUTE_TYPE` | Tipo de computação | `float16` |
| `F5_TTS_REF_AUDIO` | Áudio de referência para TTS | `data/voz_referencia/minha_voz.wav` |

### Pipeline
| Variável | Descrição | Default |
|----------|-----------|---------|
| `NICHOS_ATIVOS` | Nichos ativos (separados por vírgula) | `cultura_pop` |
| `WER_LIMITE_APROVACAO` | Limite de WER para aprovar áudio | `0.05` |
| `MAX_TENTATIVAS_TTS` | Tentativas de TTS por cena | `3` |

### Gameplay
| Variável | Descrição | Default |
|----------|-----------|---------|
| `GAMEPLAY_SEGMENT_DURATION_SEC` | Duração de cada segmento | `30` |
| `GAMEPLAY_MIN_MOTION_SCORE` | Score mínimo de movimento | `5.0` |

---

## Nichos Disponíveis

O pipeline suporta 6 nichos pré-configurados:

### 1. Cultura Pop (`cultura_pop`)
- **Foco:** Anime, filmes, jogos, lore de personagens
- **Estilo:** Explicações definitivas, listas categorizadas
- **Fontes:** r/anime, r/movies, r/gaming

### 2. Tecnologia (`tecnologia`)
- **Foco:** IA, programação, gadgets, tendências
- **Estilo:** Explicações técnicas acessíveis
- **Fontes:** r/technology, r/programming, r/artificial

### 3. Futebol (`futebol`)
- **Foco:** Táticas, história, polêmicas, análises
- **Estilo:** Análises apaixonadas mas analíticas
- **Fontes:** r/soccer, r/football, r/Brasileirao

### 4. Finanças (`financas`)
- **Foco:** Finanças pessoais, economia, investimentos
- **Estilo:** Informativo, prático, sem sensacionalismo
- **Fontes:** r/personalfinance, r/investing

### 5. Ciência (`ciencia`)
- **Foco:** Astronomia, biologia, descobertas, curiosidades
- **Estilo:** Curioso, didático, focado em fatos
- **Fontes:** r/science, r/space, r/askscience

### 6. História (`historia`)
- **Foco:** Civilizações, guerras, geopolítica, biografias
- **Estilo:** Narrativo, dramático, storytelling
- **Fontes:** r/history, r/AskHistorians, r/geopolitics

### Configurar Nichos Ativos

```bash
# Um nicho
NICHOS_ATIVOS=cultura_pop

# Múltiplos nichos
NICHOS_ATIVOS=cultura_pop,tecnologia,futebol
```

---

## Dicas e Boas Práticas

### Performance

1. **Use GPU:** Configure `WHISPER_DEVICE=cuda` para acelerar transcrição
2. **Modelo Whisper:** Use `small` ou `base` para vídeos curtos
3. **Batch processing:** Processe múltiplos vídeos em sequência
4. **Cache de assets:** Mantenha banco local bem organizado

### Qualidade

1. **Voz de referência:** Use áudio de 30-60 segundos, sem ruído, com clareza
2. **WER limite:** Mantenha em 5% para aprovação automática
3. **Revisão manual:** Sempre revise vídeos marcados com `revisao_manual_necessaria`
4. **Assets locais:** Organize por tags claras (ex: `data/assets_local/naruto/`)

### Custos

1. **Modelo local:** Use Ollama para tarefas leves (normalização)
2. **Modelo em nuvem:** Reserve para ideação e roteirização
3. **Monitoramento:** Use `python main.py --custos` regularmente
4. **Rate limits:** Configure retry adequado para evitar erros

### Gameplay

1. **Duração de segmentos:** 30 segundos é o padrão
2. **Score de movimento:** Ajuste se muitos segmentos forem rejeitados
3. **Crop por jogo:** Configure offset Y para cada jogo específico
4. **Janela de reuso:** 30 dias evita repetição excessiva

### Manutenção

1. **Backup:** Faça backup do banco semanalmente
2. **Logs:** Monitore `logs/pipeline.log` regularmente
3. **Limpeza:** Remova arquivos temporários antigos
4. **Atualizações:** Mantenha dependências atualizadas

---

## Troubleshooting

### Erro de Conexão com Banco

**Sintoma:** `connection refused` ou `database does not exist`

**Solução:**
```bash
# Verificar se PostgreSQL está rodando
docker-compose ps postgres
# ou
sudo systemctl status postgresql

# Verificar logs
docker-compose logs postgres
```

### WER Alto

**Sintoma:** Áudio rejeitado consistentemente

**Soluções:**
1. Verificar qualidade do áudio de referência
2. Reduzir `WER_LIMITE_APROVACAO` (não recomendado abaixo de 0.03)
3. Aumentar `MAX_TENTATIVAS_TTS`
4. Revisar texto de locução (pronúncias difíceis)

### GPU Não Detectada

**Sintoma:** `CUDA not available`

**Soluções:**
```bash
# Verificar driver NVIDIA
nvidia-smi

# Verificar CUDA no container
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Assets Não Encontrados

**Sintoma:** Muitas cenas marcadas para revisão manual

**Soluções:**
1. Adicionar mais assets ao banco local
2. Configurar `PEXELS_API_KEY` para fallback
3. Organizar tags corretamente (minúsculas, sem acentos)

### Renderização Lenta

**Sintoma:** Vídeos demoram muito para renderizar

**Soluções:**
1. Verificar recursos de CPU/memória
2. Usar GPU para Remotion (se disponível)
3. Reduzir qualidade/concorrência no Remotion

### Erro de Rate Limit

**Sintoma:** `RateLimitError` em chamadas LLM

**Soluções:**
1. Aguardar e tentar novamente (retry automático)
2. Distribuir chamadas ao longo do tempo
3. Usar modelo local para tarefas leves

---

## Suporte

- **Issues:** https://github.com/seu-usuario/faceless-pipeline/issues
- **Documentação:** `docs/` directory
- **Logs:** `logs/pipeline.log`

---

**Versão:** 1.0.0  
**Última Atualização:** Janeiro 2024
