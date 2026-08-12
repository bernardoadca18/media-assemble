# Prompt para Refatoração do Sistema Faceless Pipeline

## CONTEXTO DO PROJETO

Você está trabalhando no **Faceless Pipeline**, um sistema modular 100% Python para geração autônoma de vídeos "faceless" para YouTube. O sistema foi desenvolvido para substituir um workflow visual n8n, otimizado para execução local com GPU única (RTX 2060, 12GB VRAM).

### Arquitetura Geral

O sistema segue uma **arquitetura de pipeline em 5 fases**, com módulos organizados em camadas de serviço bem definidas:

```
┌─────────────────────────────────────────────────────────────────┐
│ FASE 1: TRENDS + IDEATION                                       │
│  - Coleta paralela de trends (Google Trends, Reddit RSS, YT API)│
│  - Normalização e deduplicação semântica (pgvector)             │
│  - Geração de ideias via LLM com RAG                            │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ FASE 2: SCRIPTING                                               │
│  - Geração de roteiro JSON completo (15-50 cenas)               │
│  - Validação via Pydantic schemas                               │
│  - LLM cloud (gemini-3.1-pro)                                   │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ FASE 3: AUDIO                                                   │
│  - Síntese de voz via F5-TTS (clonagem de referência)           │
│  - Validação com Faster-Whisper + WER (threshold 0.15)          │
│  - Mixagem de áudio (FFmpeg)                                    │
│  - Variação de timbre por canal (pitch/speed)                   │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ FASE 4: VISUAL ASSETS                                           │
│  - Resolução de assets (banco local → fallback Pexels API)      │
│  - Triagem via LLM                                              │
│  - Integração com gameplay backgrounds                          │
└─────────────────────────────────────────────────────────────────┘
                                    ↓
┌─────────────────────────────────────────────────────────────────┐
│ FASE 5: RENDER                                                  │
│  - Renderização via Remotion CLI (Node.js isolado)              │
│  - Estilos visuais: ken_burns, vox_motion, gameplay_bg          │
│  - Suporte a Shorts verticais (9:16)                            │
│  - Metadados SEO automáticos                                    │
└─────────────────────────────────────────────────────────────────┘
```

### Estrutura de Diretórios

```
media-assemble/
├── api/                    # FastAPI backend (interface HTTP)
│   ├── main.py            # API principal com CORS
│   └── status.py          # Router de status
├── db/                     # Camada de dados
│   ├── models.py          # Modelos SQLAlchemy + helpers
│   ├── session.py         # Gerenciamento de sessão async
│   └── migrations/        # Migrações Alembic (versões 001-007)
├── pipeline/               # Orquestração e configuração
│   ├── orchestrator.py    # Maestro do pipeline (5 fases)
│   ├── schemas.py         # Modelos Pydantic (fonte da verdade)
│   ├── config.py          # Settings via .env
│   ├── nichos.py          # Configurações por nicho
│   └── gpu_lock.py        # Semáforo para GPU
├── services/               # Módulos de serviço (uma fase cada)
│   ├── trends/            # Fase 1 — Coleta de trends
│   ├── ideation/          # Fase 1 — Geração de ideias
│   ├── scripting/         # Fase 2 — Escrita de roteiro
│   ├── audio/             # Fase 3 — Geração de áudio
│   ├── visual/            # Fase 4 — Resolução de assets
│   ├── render/            # Fase 5 — Renderização
│   ├── gameplay/          # Backgrounds de gameplay
│   └── metadata_generator.py # Subfase 8.6 — SEO
├── utils/                  # Utilitários compartilhados
│   ├── logger.py          # Logging estruturado
│   ├── litellm_client.py  # Cliente LLM unificado
│   ├── cost_tracker.py    # Rastreamento de custos
│   └── retry.py           # Lógica de retry
├── frontend/               # Interface web React
├── remotion/               # Renderização Node.js (isolado)
├── data/                   # Diretórios de dados
│   ├── assets_local/      # Banco de assets local
│   ├── gameplay_raw/      # Gravações brutas de gameplay
│   ├── gameplay_processed/# Segmentos processados
│   └── output_final/      # Vídeos renderizados
├── main.py                 # Entrada principal (CLI + scheduler)
├── requirements.txt        # Dependências Python
└── docker-compose.yml      # Setup Docker multi-serviço
```

### Stack Tecnológico

**Backend Python:**
- FastAPI + Uvicorn (API HTTP)
- SQLAlchemy 2.0 + asyncpg (PostgreSQL async)
- Alembic (migrações)
- pgvector (embeddings vetoriais)
- Pydantic 2.7 (validação de schemas)
- LiteLLM (gateway para LLMs local + cloud)

**Processamento de Áudio:**
- F5-TTS (síntese de voz com clonagem)
- Faster-Whisper (transcrição)
- FFmpeg + librosa (processamento)

**Integrações Externas:**
- Google Trends (pytrends)
- Reddit RSS (feedparser)
- YouTube Data API v3
- Pexels API (assets visuais)
- LiteLLM Proxy (Qwen local, Gemini cloud)

**Renderização:**
- Remotion 4.0 (Node.js)
- React 18

**Frontend:**
- React 19 + Vite 8
- TanStack Query 5
- Tailwind CSS + Radix UI

**GPU Lock:**
- Semáforo (1) para garantir UMA tarefa GPU por vez
- Necessário para: F5-TTS, Faster-Whisper, LLM local
- NÃO necessário para: LLM cloud, APIs externas

---

## ESTADO ATUAL DO SISTEMA

### Fases Completadas (1-6)
- ✅ Fase 1: Trends + Ideation (coleta paralela, deduplicação semântica)
- ✅ Fase 2: Scripting (geração de roteiro JSON)
- ✅ Fase 3: Audio (F5-TTS + Whisper + WER validation)
- ✅ Fase 4: Visual Assets (banco local + fallback Pexels)
- ✅ Fase 5: Render (Remotion CLI bridge)
- ✅ Fase 6: Orchestration + Observability

### Subfases Completadas (8.x)
- ✅ Subfase 8.2: Deduplicação semântica via pgvector
- ✅ Subfase 8.3: Coleta de trends multi-fonte
- ✅ Subfase 8.5: Geração de Shorts verticais
- ✅ Subfase 8.6: Metadados SEO automáticos

### Fases Recentes (9.x)
- ✅ Fase 9.1: Pipeline de ingestão de gameplay
- ✅ Fase 9.2: Resolver de gameplay para backgrounds
- ✅ Fase 9.3: Variação de timbre por canal
- ✅ Fase 9.4: Configuração de crop para Shorts

### Fase Não Iniciada
- ❌ Fase 7: Hardening, multi-nicho, deploy

---

## OBJETIVO DA REFATORAÇÃO

### 1. Modernização do Sistema de Geração de Áudio

**Contexto Atual:**
- F5-TTS para síntese de voz com clonagem de referência
- Validação via Faster-Whisper + WER (threshold 0.15)
- Até 3 tentativas com seeds diferentes
- Mixagem via FFmpeg
- Variação de timbre (pitch/speed) por canal

**Problemas Conhecidos:**
- F5-TTS não está no PyPI (instalação manual)
- Tempo de síntese variável (GPU-bound)
- WER pode falhar em edge cases (sotaques, números, siglas)
- Pouca flexibilidade em ajustes de voz por nicho

**Direções de Refatoração:**
- Avaliar alternativas modernas de TTS (Coqui TTS, Bark, Tortoise, Azure TTS, ElevenLabs API)
- Melhorar sistema de validação (WER + validação semântica + regras específicas)
- Implementar cache inteligente de áudios por texto/hash
- Sistema de perfis de voz por nicho/canal
- Métricas de qualidade de áudio (SNR, duração real vs esperada)
- Pipeline de fallback (TTS local → TTS cloud se falhar)

**Arquivos Afetados:**
- `services/audio/tts_engine.py`
- `services/audio/validator.py`
- `services/audio/pipeline_audio.py`
- `services/audio/timbre_variation.py`
- `services/audio/mixer.py`

### 2. Melhoria na Deduplicação e Grounding com Pesquisa Web

**Contexto Atual:**

**Deduplicação:**
- Embeddings via ollama-embed (nomic-embed-text)
- pgvector para busca de vizinhos mais próximos
- Threshold de similaridade cosseno >= 0.85
- Substituição via LLM (até 3 retries)
- Flag para revisão manual se falhar

**Pesquisa Web (Grounding):**
- Google Trends (pytrends, sem API key)
- Reddit RSS (feeds públicos, sem auth)
- YouTube Data API v3 (API key necessária)
- RSS Feeds nicho-específicos
- Google Custom Search

**Problemas Conhecidos:**

*Deduplicação:*
- Threshold fixo (0.85) pode ser muito rígido/flexível dependendo do nicho
- Não considera contexto temporal (notícias antigas vs recentes)
- Embeddings podem não capturar nuances semânticas específicas
- Não há feedback loop (ideias rejeitadas não melhoram o modelo)

*Grounding:*
- Google Trends instável (rate limiting, bloqueios)
- Reddit RSS limitado a feeds públicos
- YouTube API tem cota diária limitada
- Não há validação de qualidade/frescor das fontes
- Falta integração com fact-checking (para vídeos informativos)

**Direções de Refatoração:**

*Deduplicação:*
- Threshold adaptativo por nicho
- Deduplicação em múltiplas camadas:
  - Hash exato (título)
  - Similaridade semântica (embeddings)
  - Overlap temporal (mesmo tema em janela de tempo)
  - Similaridade de estrutura (LLM: comparar roteiros completos)
- Sistema de scoring de novidade (quão diferente é de conteúdos anteriores)
- Feedback loop: ideias aprovadas/rejeitadas alimentam modelo
- Deduplicação cross-nicho (evitar repetição entre canais diferentes)

*Grounding:*
- Diversificar fontes:
  - APIs de notícias (NewsAPI, GNews, MediaStack)
  - Twitter/X API (tweets trending)
  - TikTok Creative Center (trends virais)
  - Wikipedia API (fatos históricos)
  - Fact-check APIs (Google Fact Check, ClaimBuster)
- Sistema de scoring de fontes:
  - Autoridade (fontes confiáveis vs blogs)
  - Frescor (data de publicação)
  - Relevância (match com nicho)
  - Popularidade (engajamento social)
- Cache inteligente de trends (evitar requisições repetidas)
- Grounding em tempo de script:
  - Validação de fatos citados no roteiro
  - Enriquecimento com dados atualizados
  - Citação de fontes (link nos metadados)

**Arquivos Afetados:**
- `services/ideation/rag_client.py`
- `services/trends/scraper.py`
- `services/trends/normalizer.py`
- `services/scripting/writer_agent.py`
- `pipeline/schemas.py` (novos campos de metadados)

**Novos Módulos Necessários:**
- `services/grounding/fact_checker.py` (validação de fatos)
- `services/grounding/source_scorer.py` (scoring de fontes)
- `services/grounding/news_aggregator.py` (agregação de notícias)
- `services/deduplication/multi_layer.py` (deduplicação em camadas)
- `services/deduplication/feedback_loop.py` (sistema de feedback)

---

## REQUISITOS DE IMPLEMENTAÇÃO

### Princípios de Design

1. **Mantenha Compatibilidade:** Não quebre interfaces existentes sem justificativa forte
2. **Testes Antes de Código:** Escreva testes para novas funcionalidades
3. **Configuração sobre Código:** Use variáveis de ambiente para flags e thresholds
4. **Graceful Degradation:** Falhas em serviços externos não devem quebrar o pipeline
5. **Observabilidade:** Log estruturado, métricas, rastreamento de custos
6. **GPU-Conscious:** Respeite o semáforo de GPU para tarefas concorrentes
7. **Custo-Conscious:** Prefira modelos locais para tarefas simples, cloud para complexas
8. **Local-First:** Priorize recursos locais (assets, cache) sobre APIs externas

### Dependências e Restrições

**GPU Única (RTX 2060, 12GB VRAM):**
- Apenas UMA tarefa GPU por vez (semáforo em `pipeline/gpu_lock.py`)
- Modelos GPU: F5-TTS, Faster-Whisper, Qwen local
- Planejamento: Evite operações GPU concorrentes

**Cotas de API:**
- YouTube Data API v3: 10,000 unidades/dia (padrão)
- Pexels API: Rate limiting generoso (desconhecido)
- LiteLLM Proxy: Configurar rate limiting por provider

**Banco de Dados:**
- PostgreSQL 15 + pgvector
- Migrações via Alembic (versões em `db/migrations/`)

**Variáveis de Ambiente Críticas:**
```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5433/dbname

# LLM
LITELLM_BASE_URL=http://localhost:4000
LITELLM_MASTER_KEY=sk-xxx
LOCAL_MODEL_NAME=qwen-local
CLOUD_MODEL_IDEACAO=gemini-3.6-flash
CLOUD_MODEL_ROTEIRO=gemini-3.1-pro

# APIs Externas
PEXELS_API_KEY=xxx
YOUTUBE_API_KEY=xxx
GOOGLE_CSE_API_KEY=xxx  # Google Custom Search
GOOGLE_CSE_CX=xxx        # Custom Search Engine ID

# TTS
F5_TTS_REF_AUDIO=data/assets/voice_reference.wav
F5_TTS_REF_TEXT="Texto de referência para clonagem de voz"
WER_LIMITE_APROVACAO=0.15
MAX_TENTATIVAS_TTS=3

# Nichos
NICHOS_ATIVOS=animes,filmes,jogos,curiosidades
```

### Schemas Principais

**Ideia (Pydantic):**
```python
class Ideia(BaseModel):
    id: Optional[str] = None
    video_id: Optional[str] = None
    nicho: str
    topico: str
    titulo_sugerido: str
    descricao_breve: str
    fonte: str  # "google_trends", "reddit", "youtube", etc.
    data_captura: datetime
    embedding: Optional[List[float]] = None
    score_novidade: Optional[float] = None  # NOVO: scoring de novidade
    validado: bool = False  # NOVO: flag de validação
}
```

**Roteiro (Pydantic):**
```python
class Roteiro(BaseModel):
    metadata: MetadataRoteiro
    cenas: List[Cena]
    
class MetadataRoteiro(BaseModel):
    video_id: str
    nicho: str
    duracao_estimada: float  # segundos
    formato: str  # "video_principal" ou "short"
    fonte_ideia: Optional[str] = None  # NOVO: rastreamento de fonte
    fact_check_status: Optional[str] = None  # NOVO: validação de fatos
    sources: Optional[List[str]] = None  # NOVO: citação de fontes
```

**Cena (Pydantic):**
```python
class Cena(BaseModel):
    numero: int
    texto_locucao: str
    duracao_estimada: float  # segundos
    midia: MidiaRef
    efeitos_visuais: List[str]
    overlays: List[ElementoGrafico]
    audio_path: Optional[str] = None
    validacao_wer: Optional[float] = None  # NOVO: score WER da cena
```

---

## ENTREGÁVEIS ESPERADOS

### Para Refatoração de Áudio

1. **Documento de Design:** Comparação de engines TTS (local vs cloud), recomendação final
2. **Código Refatorado:**
   - `services/audio/tts_engine.py` (nova engine ou melhorias)
   - `services/audio/validator.py` (validação melhorada)
   - `services/audio/pipeline_audio.py` (pipeline robusto)
   - `services/audio/cache.py` (novo: cache de áudios)
   - `services/audio/voice_profiles.py` (novo: perfis de voz)
3. **Testes:**
   - Testes unitários para cada componente
   - Testes de integração do pipeline completo
   - Testes de performance (tempo de síntese)
4. **Métricas:**
   - Logging de tempo de síntese
   - Métricas de qualidade (WER, SNR)
   - Dashboard de monitoramento
5. **Documentação:**
   - Guia de configuração de voz por nicho
   - Troubleshooting de problemas comuns
   - Runbook de operação

### Para Deduplicação e Grounding

1. **Documento de Design:** Arquitetura de deduplicação em camadas + sistema de grounding
2. **Código Implementado:**
   - `services/deduplication/multi_layer.py` (deduplicação em camadas)
   - `services/deduplication/feedback_loop.py` (feedback loop)
   - `services/grounding/fact_checker.py` (validação de fatos)
   - `services/grounding/source_scorer.py` (scoring de fontes)
   - `services/grounding/news_aggregator.py` (agregação de notícias)
   - Refatoração de `services/ideation/rag_client.py`
   - Refatoração de `services/trends/scraper.py`
   - Atualização de `pipeline/schemas.py`
3. **Migrações de Banco:**
   - Novas tabelas para feedback de deduplicação
   - Índices para busca otimizada
   - Campos de metadados de fonte
4. **Testes:**
   - Testes unitários por componente
   - Testes de integração end-to-end
   - Testes de performance (latência de deduplicação)
5. **Configuração:**
   - Variáveis de ambiente para novos thresholds
   - Configuração de fontes por nicho
   - Flags de feature toggle
6. **Documentação:**
   - Guia de configuração de fontes
   - Explicação do algoritmo de deduplicação
   - Runbook de troubleshooting

---

## FLUXO DE TRABALHO RECOMENDADO

### Fase 1: Análise e Design (1-2 dias)
1. Ler código existente dos módulos afetados
2. Identificar pontos de extensão e limitações
3. Pesquisar engines TTS modernas e APIs de grounding
4. Elaborar documento de design com alternativas
5. Validar design com stakeholder

### Fase 2: Implementação de Áudio (2-3 dias)
1. Implementar cache de áudios (hash por texto)
2. Refatorar validação (WER + regras customizadas)
3. Implementar perfis de voz por nicho
4. Integrar sistema de fallback (local → cloud)
5. Escrever testes unitários e de integração
6. Documentar configuração e operação

### Fase 3: Implementação de Deduplicação (2-3 dias)
1. Implementar deduplicação em camadas
2. Criar sistema de feedback loop
3. Implementar scoring de novidade
4. Refatorar `rag_client.py` para usar nova arquitetura
5. Escrever testes unitários e de integração
6. Criar migrações de banco

### Fase 4: Implementação de Grounding (2-3 dias)
1. Implementar agregador de notícias
2. Criar scorer de fontes
3. Implementar validação de fatos
4. Integrar com `writer_agent.py`
5. Atualizar schemas com metadados de fonte
6. Escrever testes e documentação

### Fase 5: Integração e Testes (1-2 dias)
1. Testes end-to-end do pipeline completo
2. Testes de performance e carga
3. Validação de observabilidade (logs, métricas)
4. Documentação final
5. Deploy em ambiente de staging

---

## CRITÉRIOS DE ACEITAÇÃO

### Critérios Técnicos

1. **Cobertura de Testes:** Mínimo 80% de cobertura em novos módulos
2. **Performance:** 
   - Latência de deduplicação < 500ms (p95)
   - Tempo de síntese de áudio mantido ou reduzido
3. **Observabilidade:**
   - Logs estruturados em todos os novos módulos
   - Métricas de negócio (novidade, qualidade de fonte, WER)
4. **Compatibilidade:**
   - Pipeline existente continua funcionando
   - Migrações de banco reversíveis
   - Flags de feature toggle para rollback

### Critérios Funcionais

1. **Áudio:**
   - Cache de áudios reduz sínteses repetidas em > 70%
   - WER médio < 0.10
   - Suporte a pelo menos 3 perfis de voz distintos
2. **Deduplicação:**
   - Precisão > 95% (poucos falsos positivos)
   - Recall > 90% (poucos duplicados não detectados)
   - Threshold adaptativo por nicho
3. **Grounding:**
   - Mínimo 5 fontes de trends ativas
   - Scoring de fonte funcional (autoridade, frescor, relevância)
   - Validação de fatos implementada (pelo menos 50% dos roteiros)

---

## RISCOS E MITIGAÇÕES

### Risco 1: Incompatibilidade de Engine TTS
**Mitigação:** Manter F5-TTS como fallback, implementar interface abstrata de TTS

### Risco 2: Rate Limiting de APIs Externas
**Mitigação:** Implementar backoff exponencial, cache agressivo, fallback para fontes alternativas

### Risco 3: Degradação de Performance
**Mitigação:** Testes de carga, profiling de GPU, otimização de queries de banco

### Risco 4: Falsos Positivos em Deduplicação
**Mitigação:** Threshold conservador, revisão manual de edge cases, feedback loop para ajuste

### Risco 5: Aumento de Custos (LLM Cloud)
**Mitigação:** Usar modelos locais para tarefas simples, monitorar custos via `utils/cost_tracker.py`

---

## PERGUNTAS PARA DISCUSSÃO

1. **Priorização:** Qual refatoração deve vir primeiro (áudio ou deduplicação/grounding)?
2. **Engine TTS:** Preferência por solução 100% local (F5-TTS, Coqui) ou híbrida (local + cloud API)?
3. **Fontes de Trends:** Quais fontes são prioritárias (notícias, redes sociais, APIs específicas)?
4. **Validação de Fatos:** Nível de rigor (apenas checagem básica ou validação profunda com múltiplas fontes)?
5. **Perfis de Voz:** Quantos perfis distintos são necessários (por nicho, por canal, por tipo de vídeo)?
6. **Rollout:** Estratégia de deploy (feature flags, rollout gradual, blue-green)?
7. **Métricas:** Quais KPIs são mais importantes para medir sucesso da refatoração?

---

## PRÓXIMOS PASSOS

1. **Validar Entendimento:** Revisar este prompt e confirmar se está completo
2. **Responder Perguntas:** Discutir as questões acima para alinhar prioridades
3. **Iniciar Design:** Começar pela análise detalhada do módulo prioritário
4. **Implementação Iterativa:** Seguir fluxo de trabalho em fases, com entregas incrementais

---

**Nota:** Este prompt é um documento vivo. Atualize conforme novas decisões forem tomadas durante a refatoração.
