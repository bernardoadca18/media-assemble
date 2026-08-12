# Relatório Técnico - Pipeline de Geração de Vídeos Automatizados

## 1. Contexto do Projeto

O **media-assemble** é um sistema de geração automatizada de vídeos curtos (formato Shorts/Reels) que integra múltiplos microsserviços de IA para transformar tendências de internet em vídeos narrados prontos para publicação. O projeto opera em um fluxo de pipeline orquestrado, desde a coleta de tendências até a síntese de voz e validação de qualidade.

O sistema é composto por dois repositórios principais:
- **media-assemble**: Pipeline principal, orquestração, banco de dados e lógica de negócio
- **voice-workshop**: Serviço dedicado à síntese de voz com Kokoro TTS + Seed-VC

---

## 2. Arquitetura de Microsserviços

### 2.1 Banco de Dados (PostgreSQL + pgvector)

**Serviço**: `postgres`
**Imagem**: `pgvector/pgvector:pg16`

**Função**: Armazenamento persistente com suporte a embeddings vetoriais para busca semântica.

**Schema Principal**:
- `dados.videos_ideias`: Ideias de vídeos com embeddings (1024 dimensões, mxbai-embed-large)
- `dados.videos`: Metadados de vídeos gerados
- `dados.roteiros`: Roteiros estruturados por cenas
- `dados.ideias_manuais`: Ideias inseridas manualmente com prioridade e status

**Extensões**:
- `pgvector`: Busca por similaridade semântica (HNSW index)
- `btree_gin`: Índices compostos

### 2.2 LiteLLM Proxy

**Porta**: 4000
**Função**: Roteamento centralizado de requisições para modelos LLM e embeddings.

**Modelos Configurados**:
- `gemini-3.6-flash`: Ideação e análise rápida (cloud)
- `gemini-3.1-pro`: Geração de roteiros (cloud)
- `ollama-embed`: Embeddings locais via Ollama (mxbai-embed-large, 1024 dims)

**Vantagens**:
- Fallback automático entre modelos
- Rate limiting centralizado
- Custos unificados em um único proxy

### 2.3 Pipeline de Voz (voice-workshop)

**Serviços Docker**:
- `kokoro`: Servidor TTS Kokoro (porta 8880)
- `seedvc`: Conversão de voz/estilo (GPU)

**Fluxo de Síntese**:
1. Texto → Kokoro TTS → Áudio base
2. Áudio base + voz de referência → Seed-VC → Áudio final com voz personalizada

**Características**:
- Lock de GPU para evitar concorrência
- Retry automático para código 409 (GPU ocupada)
- Timeout configurável (600s por cena)
- Checkpoints de voz treinados por `run_name`

---

## 3. Camadas do Pipeline

### 3.1 Coleta de Tendências (`services/trends/`)

**Componentes**:
- `scraper.py`: Coleta de Reddit RSS, Google Trends (opcional), YouTube Trending (opcional)
- `rss_sources.py`: Feeds RSS de nichos específicos
- `normalizer.py`: Normalização via LLM para padronizar formato

**Fontes Ativas**:
- Reddit RSS (múltiplos subreddits por nicho)
- RSS de nichos (feeds personalizados)

**Fontes Desativadas** (sem API keys):
- YouTube Trending API
- Google Trends
- Google Custom Search Engine (CSE)

### 3.2 Ideação (`services/ideation/`)

**Componentes**:
- `agent.py`: Agente de geração de ideias via LLM
- `rag_client.py`: Busca semântica para evitar duplicatas

**Fluxo**:
1. Carrega ideias manuais pendentes (tabela `ideias_manuais`)
2. Gera ideias via LLM a partir das tendências coletadas
3. Verifica duplicidade semântica via embeddings (similaridade de cosseno)
4. Rankeia ideias por potencial de engajamento

**Fallback**: Se Ollama indisponível, opera sem verificação de duplicidade.

### 3.3 Roteirização (`services/scripting/`)

**Componentes**:
- `writer_agent.py`: Geração de roteiros estruturados

**Estrutura do Roteiro**:
```json
{
  "titulo": "Título do vídeo",
  "cenas": [
    {
      "cena_id": 1,
      "texto": "Texto a ser narrado",
      "duracao_estimada": 15.0
    }
  ]
}
```

**Modelo**: gemini-3.1-pro (via LiteLLM)

### 3.4 Pipeline de Áudio (`services/audio/`)

**Componentes**:
- `pipeline_audio.py`: Orquestração da síntese e validação
- `voice_pipeline_client.py`: Cliente HTTP para Kokoro+Seed-VC
- `validator.py`: Validação via Faster-Whisper + WER

**Fluxo por Cena**:
1. Envia texto para `voice-workshop` (POST /narrar)
2. Aguarda áudio sintetizado (timeout: 600s)
3. Transcreve áudio com Faster-Whisper (CPU, int8)
4. Calcula Word Error Rate (WER) contra texto original
5. Se WER ≤ 0.15: aprova cena
6. Se WER > 0.15: regenera (máx. 3 tentativas)

**Configuração Whisper**:
- Device: CPU (sem CUDA disponível)
- Compute type: int8 (compatível com CPU)
- Modelo: medium

### 3.5 Orquestrador (`pipeline/orchestrator.py`)

**Fluxo Completo**:
```
[Coleta Tendências] → [Ideação] → [Roteirização] → [Áudio] → [Assembly] → [Publicação]
```

**Características**:
- Memória persistente entre estágios (tabela `pipeline_memoria`)
- Tratamento de erros com continuidade
- Logging estruturado em JSON
- Métricas de custo por requisição LLM

---

## 4. Análise de Performance

### 4.1 Problemas Identificados

#### 4.1.1 Timeout no Pipeline de Voz (Seed-VC)

**Sintoma**: Segunda cena do roteiro sistematicamente atinge timeout (300s interno + 120s HTTP).

**Logs de Erro**:
```
PipelineInternoFalhou: Erro interno no pipeline: Timeout (300s) executando comando em seedvc
PipelineInternoFalhou: Erro interno no pipeline: HTTPConnectionPool(host='localhost', port=8880): Read timed out. (read timeout=120)
```

**Observações**:
- Cena 1: Processada em ~32 segundos (sucesso)
- Cena 2: Timeout após >300 segundos (falha)
- Padrão se repete em todas as execuções

**Hipóteses**:

1. **Exaustão de Memória GPU**:
   - Seed-VC pode não estar liberando VRAM entre requisições
   - Acúmulo progressivo de tensores residuais
   - Necessidade de reinicialização do container `seedvc`

2. **Texto Mais Longo na Cena 2**:
   - Duração do áudio correlaciona com tempo de processamento
   - Seed-VC tem complexidade não-linear
   - Textos longos podem exceder limites de memória

3. **Conflito de Recursos GPU**:
   - Whisper rodando em CPU, mas pode haver processos GPU concorrentes
   - Kokoro e Seed-VC competem pelo mesmo dispositivo
   - Lock de GPU no voice-workshop pode não estar funcionando corretamente

4. **Degradacao Progressiva**:
   - Primeira requisição usa cache/fases iniciais otimizadas
   - Requisições subsequentes perdem otimizações
   - Possível memory leak no serviço

#### 4.1.2 Modelo Local Indisponível

**Sintoma**: `litellm.erro_permanente_local` em toda execução.

**Causa**: Ollama não está rodando ou modelo `mxbai-embed-large` não está carregado.

**Impacto**:
- Normalização de tendências falha (usa fallback simples)
- Verificação de duplicidade semântica falha
- Pipeline continua operando, mas sem garantia de unicidade

**Solução**: Iniciar Ollama antes do pipeline:
```bash
ollama serve
ollama pull mxbai-embed-large
```

#### 4.1.3 Configuração de Compute Type

**Problema Original**: Whisper tentando usar CUDA com `float16`, mas CUDA não disponível.

**Erro**:
```
ValueError: Requested float16 compute type, but target device or backend do not support efficient float16 computation.
```

**Solução Aplicada**:
- `WHISPER_DEVICE=cpu`
- `WHISPER_COMPUTE_TYPE=int8`

**Trade-off**:
- CPU int8 é ~5-10x mais lento que GPU float16
- Porém, funcional sem dependência de CUDA
- Tempo de transcrição aceitável para áudios curtos (<30s)

### 4.2 Tempos de Execução Observados

| Estágio | Tempo | Observações |
|---------|-------|-------------|
| Coleta de Tendências | 1-2s | RSS feeds rápidos |
| Ideação | 15-20s | LLM cloud (gemini-3.6-flash) |
| Roteirização | 40-50s | LLM cloud (gemini-3.1-pro) |
| Áudio Cena 1 (narração) | 32s | Kokoro + Seed-VC |
| Áudio Cena 1 (validação) | 10s | Whisper CPU int8 |
| Áudio Cena 2 (narração) | >300s | TIMEOUT |

### 4.3 Gargalos Identificados

1. **Seed-VC é o principal gargalo**:
   - Processamento não-otimizado para textos médios/longos
   - Possível vazamento de memória entre requisições
   - Sem mecanismo de cleanup automático

2. **Whisper em CPU**:
   - Funcional mas lento
   - Aceitável para o volume atual (poucas cenas por vídeo)
   - Escalabilidade comprometida para volumes maiores

3. **Sem paralelismo no pipeline de áudio**:
   - Cenas processadas sequencialmente
   - Não aproveita múltiplos cores para Whisper
   - Tempo total = soma de todas as cenas

---

## 5. Recomendações

### 5.1 Críticas (Curto Prazo)

1. **Investigar memória GPU no Seed-VC**:
   ```bash
   docker exec seedvc nvidia-smi
   docker compose restart seedvc
   ```

2. **Reduzir tamanho das cenas**:
   - Dividir textos longos em múltiplas cenas curtas
   - Limite sugerido: 15-20 segundos por cena
   - Reduz carga no Seed-VC

3. **Implementar cleanup entre requisições**:
   - Reiniciar container Seed-VC a cada vídeo
   - Adicionar endpoint `/cleanup` no voice-workshop

### 5.2 Melhorias de Performance (Médio Prazo)

1. **Whisper em GPU**:
   - Instalar CUDA toolkit completo (libcublas.so.12)
   - Usar `float16` para máxima performance
   - Reduzir tempo de validação de 10s para <1s

2. **Processamento paralelo de cenas**:
   - ThreadPoolExecutor para Whisper
   - Lock de GPU apenas para Seed-VC
   - Múltiplas cenas validadas simultaneamente

3. **Cache de embeddings**:
   - Armazenar embeddings calculados
   - Evitar recálculo para textos similares
   - Reduzir carga no Ollama

### 5.3 Arquiteturais (Longo Prazo)

1. **Separação de responsabilidades**:
   - Serviço dedicado para Kokoro (TTS)
   - Serviço dedicado para Seed-VC (voice conversion)
   - Escalar independentemente

2. **Queue-based processing**:
   - Redis/RabbitMQ para fila de cenas
   - Workers independentes para cada estágio
   - Retry automático com backoff exponencial

3. **Observabilidade**:
   - Métricas de tempo por estágio (Prometheus)
   - Tracing distribuído (Jaeger/Zipkin)
   - Alertas para timeouts frequentes

---

## 6. Status Atual do Sistema

### 6.1 Funcionalidades Operacionais

- ✅ Coleta de tendências (Reddit RSS, nichos RSS)
- ✅ Ideação via LLM cloud
- ✅ Geração de roteiros estruturados
- ✅ Síntese de voz (primeira cena)
- ✅ Validação de áudio via Whisper (CPU)
- ✅ Banco de dados com embeddings vetoriais
- ✅ Lock de GPU para evitar concorrência
- ✅ Retry automático para falhas transientes

### 6.2 Limitações Conhecidas

- ⚠️ Seed-VC com timeouts em cenas subsequentes
- ⚠️ Ollama precisa ser iniciado manualmente
- ⚠️ APIs do Google/YouTube desativadas (sem keys)
- ⚠️ Whisper em CPU (sem aceleração GPU)
- ⚠️ Processamento sequencial de cenas

### 6.3 Configuração Atual

```env
# Áudio
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WER_LIMITE_APROVACAO=0.15
MAX_TENTATIVAS_TTS=3

# Voice Pipeline
VOICE_PIPELINE_URL=http://localhost:9000
VOICE_PIPELINE_TIMEOUT=600
VOICE_PIPELINE_MAX_RETRIES=5
VOICE_PIPELINE_RETRY_DELAY=30.0

# Modelos
CLOUD_MODEL_IDEACAO=gemini-3.6-flash
CLOUD_MODEL_ROTEIRO=gemini-3.1-pro
LOCAL_MODEL_NAME=qwen-local
```

---

## 7. Conclusão

O pipeline está funcional e integrado, com todos os microsserviços operando em conjunto. Os principais problemas de configuração (CUDA, ENUM, vetores) foram resolvidos. O gargalo atual está no serviço Seed-VC, que apresenta degradação de performance após a primeira requisição.

A arquitetura é sólida e bem estruturada, com separação clara de responsabilidades, tratamento de erros robusto e mecanismos de retry. Para produção, recomenda-se foco em otimização do Seed-VC e implementação de processamento paralelo para escalar o volume de vídeos gerados.
