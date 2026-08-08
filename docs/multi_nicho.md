# Subfase 8.7 — Multi-nicho em Produção

## Visão Geral

Esta documentação descreve a operação do pipeline com múltiplos nichos simultâneos, incluindo considerações de hardware, gerenciamento de GPU e boas práticas.

## Nichos Disponíveis

### Nichos Ativos (padrão)

1. **cultura_pop** - Filmes, séries, animes, celebridades
   - Categoria Google Trends: 16 (Entertainment)
   - Estilo visual predominante: `ken_burns`
   - Subreddits: r/movies, r/television, r/anime, r/popheads

2. **tecnologia** - Tech, inovação, IA, gadgets
   - Categoria Google Trends: 5 (Tech)
   - Estilo visual predominante: `vox_motion` (comparativos, timelines)
   - Subreddits: r/technology, r/gadgets, r/artificial, r/Futurology

3. **futebol** - Táticas, história, análises de times/jogadores
   - Categoria Google Trends: 20 (Sports)
   - Estilo visual: `ken_burns` + `vox_motion` (estatísticas)
   - Subreddits: r/soccer, r/football, r/Brasileirao

4. **financas** - Finanças pessoais, economia, investimentos (NOVO)
   - Categoria Google Trends: 7 (Finance)
   - Estilo visual predominante: `vox_motion` (números, gráficos)
   - Subreddits: r/personalfinance, r/financialindependence, r/investing, r/economy
   - **Forte em vox_motion**: comparativos de juros, tabelas de evolução financeira

5. **ciencia** - Astronomia, biologia, física, descobertas (NOVO)
   - Categoria Google Trends: 11 (Science)
   - Estilo visual: `ken_burns` (galáxias, células) + `vox_motion` (escalas, dados)
   - Subreddits: r/science, r/space, r/askscience, r/curiosity
   - **Evergreen**: baixo risco autoral, conteúdo atemporal

6. **historia** - Civilizações, guerras, geopolítica, biografias (NOVO)
   - Categoria Google Trends: 24 (Society)
   - Estilo visual predominante: `vox_motion` (timelines, mapas)
   - Subreddits: r/history, r/AskHistorians, r/geopolitics, r/MapPorn
   - **Farto material de domínio público**: pinturas históricas, mapas antigos

## Configuração

### Habilitar Múltiplos Nichos

No `.env`, configure `NICHOS_ATIVOS` separando por vírgula:

```bash
# Todos os nichos ativos
NICHOS_ATIVOS=cultura_pop,tecnologia,futebol,financas,ciencia,historia

# Apenas 4 nichos (recomendado para início)
NICHOS_ATIVOS=cultura_pop,tecnologia,financas,ciencia
```

### Agendamento por Nicho

O scheduler (main.py) executa um vídeo por nicho de forma round-robin. Com 4 nichos ativos, cada um gera 1 vídeo a cada 4 ciclos do scheduler.

### Hardware Recomendado

**Especificações de Referência (RTX 2060 12GB):**

- **VRAM Total**: 12GB
- **VRAM Disponível para Pipeline**: ~10GB (reservar 2GB para sistema)
- **Concorrência**: Máximo 1 processo GPU por vez

**Consumo por Componente:**

| Componente | VRAM | Duração (aprox.) |
|------------|------|------------------|
| F5-TTS (por cena) | ~1.5GB | 3-10s por cena |
| Faster-Whisper | ~2GB | 1-2s por cena |
| Chrome (Remotion) | ~2-3GB | 5-10s por vídeo |
| **Total por vídeo** | ~5-7GB | Variável |

**Impacto dos Shorts (Subfase 8.5):**
- Shorts adicionam +1-2 processos de renderização por vídeo longo
- Tempo adicional de GPU: +30-60s por vídeo longo
- VRAM adicional: desprezível (mesmo Chrome, reutilizado)

## Gerenciamento de GPU (gpu_lock.py)

O módulo `pipeline/gpu_lock.py` implementa um semáforo global que serializa todas as operações que usam GPU:

```python
# Uso interno do pipeline
async with gpu_task("f5-tts-cena-03"):
    # Código que usa GPU (F5-TTS, Whisper, Remotion)
    ...
```

**Funcionamento:**

1. **F5-TTS**: Adquire o lock para cada cena do roteiro (10-20 cenas)
2. **Faster-Whisper**: Adquire o lock para validar cada áudio gerado
3. **Remotion (Chrome)**: Adquire o lock durante renderização do vídeo

**Logs de Monitoramento:**

```
INFO gpu_lock.waiting task=f5-tts-cena-03
INFO gpu_lock.started task=f5-tts-cena-03
INFO gpu_lock.finished task=f5-tts-cena-03
```

**Detecção de Problemas:**

- Se `waiting` demorar muito para virar `started`: concorrência alta
- Se `finished` não aparecer: deadlock ou crash no processo de GPU
- Monitore `nvidia-smi` durante execução para validar consumo

## Testando Múltiplos Nichos

### Teste de Estresse (4 nichos simultâneos)

```bash
# Executar uma vez com cada nicho
for nicho in cultura_pop tecnologia financas ciencia; do
    python main.py --run-once --nicho $nicho
done
```

### Monitoramento em Produção

```bash
# Verificar logs do gpu_lock
grep "gpu_lock" logs/pipeline.log | tail -50

# Verificar tempo entre waiting e started
grep -A1 "gpu_lock.waiting" logs/pipeline.log | grep "started"

# Monitorar VRAM em tempo real
watch -n 1 nvidia-smi
```

### Validação de Carga (RTX 2060)

**Teste Recomendado:**

1. Habilitar 4 nichos: `NICHOS_ATIVOS=cultura_pop,tecnologia,financas,ciencia`
2. Habilitar Shorts: `GERAR_SHORTS_AUTOMATICO=true`
3. Executar por 48-72 horas contínuas
4. Monitorar:
   - Logs de `gpu_lock` para detectar conflitos
   - `nvidia-smi` para estouro de VRAM
   - Taxa de sucesso das execuções (`salvar_execucao`)

**Critérios de Sucesso:**

- ✓ Sem deadlock de GPU (todos `waiting` viram `started`)
- ✓ Sem estouro de VRAM (< 11.5GB pico)
- ✓ Taxa de sucesso > 95%
- ✓ Shorts renderizando corretamente

## Adicionando Novo Nicho

### Passo a Passo

1. **Adicionar configuração em `pipeline/nichos.py`:**

```python
"novo_nicho": ConfigNicho(
    nome="novo_nicho",
    prompt_ideacao="""...""",  # Seguir padrão dos nichos existentes
    prompt_roteiro_adicional="""...""",
    prompt_roteiro_short="""...""",  # OBRIGATÓRIO desde Subfase 8.5
    categoria_google_trends=XX,  # Ver tabela em services/trends/scraper.py
    subreddits_sugeridos=["r/sub1", "r/sub2"],  # Desde Subfase 8.3
),
```

2. **Atualizar `.env.example`:**

```bash
NICHOS_ATIVES=cultura_pop,tecnologia,...,novo_nicho
```

3. **Criar banco de assets inicial:**

```bash
mkdir -p data/assets_local/{tag1}/{tag2}
# Adicionar imagens/vídeos de domínio público
```

4. **Testar individualmente:**

```bash
python main.py --run-once --nicho novo_nicho
```

5. **Validar em produção:**

```bash
# Adicionar temporariamente aos nichos ativos
NICHOS_ATIVOS=cultura_pop,novo_nicho
# Executar por 24 horas monitorando logs
```

### Critérios para Novo Nicho

- **Material de domínio público**: Evitar direitos autorais
- **Estilo visual compatível**: `ken_burns` ou `vox_motion`
- **Sem dependência de pessoas reais recentes**: Faceless-friendly
- **Prompt de Short**: Obrigatório desde Subfase 8.5
- **Subreddits sugeridos**: Para enriquecimento de tendências

## Troubleshooting

### GPU Lock Demorando Muito

**Sintoma:** `gpu_lock.waiting` não vira `started` por minutos

**Causas:**
- Processo de GPU travado (Chrome, TTS, Whisper)
- Deadlock em subprocesso

**Solução:**
```bash
# Identificar processo travado
nvidia-smi --query-compute-apps=pid --format=csv

# Matar processo se necessário
kill -9 <PID>
```

### Estouro de VRAM

**Sintoma:** Crash com "CUDA out of memory"

**Soluções:**
1. Reduzir número de nichos ativos
2. Desativar Shorts temporariamente: `GERAR_SHORTS_AUTOMATICO=false`
3. Usar modelo Whisper menor: `WHISPER_MODEL_SIZE=small`

### Shorts Não Gerando

**Sintoma:** Logs mostram `pipeline.shorts_falhou`

**Causas:**
- LLM não conseguiu identificar clips
- Duração dos clips fora do limite (25-58s)
- Renderização falhou

**Debug:**
```bash
grep "shorts" logs/pipeline.log | tail -20
```

## Métricas de Produção

Após período de teste (recomendado 72 horas), coletar:

```sql
-- Taxa de sucesso por nicho
SELECT 
    nicho,
    COUNT(*) as total,
    SUM(CASE WHEN sucesso THEN 1 ELSE 0 END) as sucessos,
    ROUND(100.0 * SUM(CASE WHEN sucesso THEN 1 ELSE 0 END) / COUNT(*), 2) as taxa_sucesso
FROM dados.execucoes_pipeline
WHERE criado_em > NOW() - INTERVAL '3 days'
GROUP BY nicho
ORDER BY taxa_sucesso DESC;

-- Tempo médio por nicho
SELECT 
    nicho,
    AVG(EXTRACT(EPOCH FROM (atualizado_em - criado_em))) as tempo_medio_segundos
FROM dados.execucoes_pipeline
WHERE sucesso = true
    AND criado_em > NOW() - INTERVAL '3 days'
GROUP BY nicho;
```

---

## Histórico de Revisões

- **2026-08-08**: Documentação inicial (Subfase 8.7)
  - Adicionados nichos: financas, ciencia, historia
  - Atualizado `.env.example` com lista de nichos disponíveis
  - Documentado gerenciamento de GPU com Shorts
