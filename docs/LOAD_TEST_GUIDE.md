# Guia de Teste de Carga — Fase 10.1

## Objetivo

Validar que o pipeline opera corretamente com múltiplos estilos visuais simultâneos e documentar tempos de renderização para calibrar throughput diário esperado.

---

## Pré-requisitos

1. **Ambiente configurado**
   - PostgreSQL rodando
   - Redis (se aplicável)
   - GPU disponível (CUDA)
   - FFmpeg instalado

2. **Dados de teste preparados**
   - Gameplay footage em `data/gameplay_raw/`
   - Voz de referência em `data/voz_referencia/`
   - Assets locais em `data/assets_local/`

3. **Nichos configurados**
   - Pelo menos 3 nichos ativos em `NICHOS_ATIVOS`
   - Cada nicho usando estilo visual diferente

---

## Configuração do Teste

### 1. Preparar nichos com estilos diferentes

Editar `pipeline/nichos.py` para garantir que cada nicho use um estilo visual:

```python
# Exemplo de configuração
"cultura_pop": ConfigNicho(
    # ... usar ken_burns (padrão)
),

"tecnologia": ConfigNicho(
    # ... configurar para usar vox_motion
),

"futebol": ConfigNicho(
    # ... configurar para usar gameplay_bg
    gameplay_intensidade_preferida="moderado",
),
```

### 2. Configurar ambiente de teste

```bash
# .env
NICHOS_ATIVOS=cultura_pop,tecnologia,futebol

# GPU
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16

# Paralelismo (se aplicável)
MAX_CONCURRENT_VIDEOS=3
```

### 3. Verificar estado inicial

```bash
# Limpar logs anteriores
rm logs/pipeline.log

# Verificar banco limpo
psql -d faceless_pipeline -c "SELECT COUNT(*) FROM videos WHERE status = 'processando';"

# Verificar GPU disponível
nvidia-smi
```

---

## Execução do Teste

### Teste 1: Processamento sequencial

```bash
# Executar 1 vídeo de cada nicho
python main.py --run-once --nicho cultura_pop
python main.py --run-once --nicho tecnologia
python main.py --run-once --nicho futebol
```

**Métricas a coletar:**
- Tempo total por vídeo
- Tempo de cada fase (ideação, roteiro, áudio, render)
- Uso de GPU
- Uso de memória

### Teste 2: Processamento paralelo (se suportado)

```bash
# Executar múltiplos vídeos simultaneamente
python main.py --run-once &
python main.py --run-once &
python main.py --run-once &
wait
```

**Verificar:**
- Lock de GPU funcionando (`data/gpu.lock`)
- Sem conflitos de recursos
- Logs sem erros de concorrência

### Teste 3: Carga contínua (24h)

```bash
# Executar em modo agendado por 24h
python main.py &
# Aguardar 24h
kill %1
```

**Métricas a coletar:**
- Total de vídeos processados
- Taxa de erro
- Tempo médio de processamento
- Uso de recursos ao longo do tempo

---

## Coleta de Métricas

### Script de monitoramento

```bash
#!/bin/bash
# monitor.sh

while true; do
    echo "=== $(date) ===" >> metrics.log
    
    # GPU
    nvidia-smi --query-gpu=utilization.gpu,memory.used --format=csv >> metrics.log
    
    # Processos
    ps aux | grep python | grep main.py >> metrics.log
    
    # Disco
    df -h data/ >> metrics.log
    
    sleep 60
done
```

### Parsing de logs

```bash
# Tempo de processamento por fase
grep "pipeline.concluido" logs/pipeline.log | jq -r '.duration'

# Tempo de renderização por estilo
grep "renderizar_video" logs/pipeline.log | jq -r '.duration'

# Erros
grep "ERROR" logs/pipeline.log
```

---

## Resultados Esperados

### Métricas de referência (estimativas)

| Fase | Tempo estimado | Observações |
|------|----------------|-------------|
| Ideação | 10-30s | Depende do modelo LLM |
| Roteirização | 30-60s | Por cena |
| TTS (por cena) | 5-15s | Depende da GPU |
| Validação WER | 3-10s | Por cena |
| **Áudio total** | 2-5min | Para 10-15 cenas |
| Asset resolution | 1-5min | Por cena |
| **Renderização** | 5-15min | Depende do estilo |

### Por estilo visual

| Estilo | Tempo adicional | Motivo |
|--------|-----------------|---------|
| ken_burns | Base | Imagem estática |
| vox_motion | +10-20% | Elementos gráficos |
| gameplay_bg | +50-100% | Segmentação + concatenação |

---

## Validação do Lock de GPU

### Verificar serialização

```python
# Teste manual do lock
from pipeline.gpu_lock import GPULock

lock = GPULock()

# Processo 1
assert lock.acquire(timeout=60), "Lock não adquirido"
print("Processo 1: Lock adquirido")

# Processo 2 (deve falhar)
# Em outro terminal:
# python -c "from pipeline.gpu_lock import GPULock; l = GPULock(); print(l.acquire(timeout=5))"
# Deve retornar False

lock.release()
```

### Verificar locks órfãos

```bash
# Listar locks
ls -la data/*.lock

# Remover lock órfão (cuidado!)
rm data/gpu.lock
```

---

## Interpretação dos Resultados

### Sinais de problema

- **Tempo de processamento crescendo:** Possível memory leak
- **Erros de GPU:** Recursos insuficientes ou lock não funcionando
- **WER alto:** Problema na voz de referência ou modelo TTS
- **Renderização lenta:** Verificar configuração do Remotion

### Ajustes recomendados

- **Throughput baixo:** Reduzir `MAX_CONCURRENT_VIDEOS`
- **GPU sobrecarregada:** Aumentar tempo entre vídeos
- **Disco cheio:** Limpar arquivos temporários

---

## Relatório de Teste

Após execução, documentar:

```markdown
## Relatório de Teste de Carga — [DATA]

### Configuração
- Nichos testados: [lista]
- Duração do teste: [horas]
- Hardware: [especificações]

### Resultados

| Métrica | Valor |
|---------|-------|
| Vídeos processados | X |
| Taxa de sucesso | Y% |
| Tempo médio (ken_burns) | Z min |
| Tempo médio (vox_motion) | W min |
| Tempo médio (gameplay_bg) | V min |
| Uso médio GPU | N% |
| Pico de memória | M GB |

### Problemas encontrados
- [Lista de problemas]

### Recomendações
- [Lista de ajustes]

### Throughput diário esperado
- [Cálculo baseado nos resultados]
```

---

## Checklist de Validação

- [ ] Lock de GPU funciona corretamente
- [ ] Sem erros de concorrência nos logs
- [ ] Tempo de processamento estável ao longo do tempo
- [ ] Uso de recursos dentro dos limites
- [ ] Todos os estilos visuais processados com sucesso
- [ ] Taxa de erro < 5%
- [ ] WER médio < 5%
- [ ] Documentação de tempos por estilo
