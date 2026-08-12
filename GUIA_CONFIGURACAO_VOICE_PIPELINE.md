# Guia de Configuração: Pipeline de Voz Kokoro+Seed-VC

## Visão Geral

Este guia orienta a configuração do novo pipeline de geração de voz baseado em Kokoro+Seed-VC, que substitui o F5-TTS.

---

## Pré-requisitos

### No Servidor de Voz (Orchestrator)

1. **Docker e Docker Compose** instalados
2. **GPU NVIDIA** com CUDA (RTX 2060+ recomendado)
3. **NVIDIA Container Toolkit** para GPU em containers
4. **Checkpoints treinados** em `data/checkpoints/`

### No Media-Assemble

1. **Python 3.11+**
2. **httpx** (`pip install httpx`)
3. **Faster-Whisper** para validação WER
4. **Acesso HTTP** ao servidor de voz

---

## Configuração do Servidor de Voz

### 1. Estrutura de Diretórios

```
orchestrator/
├── data/
│   ├── checkpoints/
│   │   ├── ft_model.pth              # Modelo base Seed-VC
│   │   ├── minha_voz_v1.yml          # Config do checkpoint treinado
│   │   └── voz_anime_v1.yml          # Outro checkpoint (opcional)
│   ├── reference/
│   │   └── voz_referencia.wav        # Áudio de referência para clonagem
│   ├── work/                          # Diretório de trabalho (auto-criado)
│   └── final_output/                  # Saída temporária (auto-criado)
├── docker-compose.yml
├── Dockerfile.seedvc
└── orchestrator.py                    # FastAPI app
```

### 2. Treinar Checkpoint de Voz

```bash
# 1. Preparar áudio de referência (10-30s de alta qualidade)
# 2. Colocar em data/reference/voz_referencia.wav
# 3. Executar fine-tuning do Seed-VC
python train_seedvc.py \
  --reference_audio data/reference/voz_referencia.wav \
  --run_name minha_voz_v1 \
  --epochs 1000
```

### 3. Iniciar Serviços

```bash
# Iniciar containers Kokoro e Seed-VC
docker-compose up -d

# Iniciar orchestrator
uvicorn orchestrator:app --host 0.0.0.0 --port 9000
```

### 4. Verificar Saúde

```bash
curl http://localhost:9000/health
# Esperado: {"status": "ok"}
```

---

## Configuração do Media-Assemble

### 1. Variáveis de Ambiente

Crie ou atualize o arquivo `.env`:

```bash
# === Pipeline de Voz (Kokoro+Seed-VC) ===

# URL do serviço de voz
VOICE_PIPELINE_URL=http://localhost:9000

# Run name padrão (checkpoint a usar)
VOICE_PIPELINE_RUN_NAME_DEFAULT=minha_voz_v1

# Timeout por cena (segundos)
VOICE_PIPELINE_TIMEOUT=300

# Retries para GPU ocupada (código 409)
VOICE_PIPELINE_MAX_RETRIES=3
VOICE_PIPELINE_RETRY_DELAY=2.0

# === Validação WER (Faster-Whisper) ===
WER_LIMITE_APROVACAO=0.15
MAX_TENTATIVAS_TTS=3

# === Whisper (para validação) ===
WHISPER_MODEL_SIZE=medium
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

### 2. Configurar Voz por Nicho

Edite `pipeline/nichos.py`:

```python
NICHOS = {
    "animes": ConfigNicho(
        nome="animes",
        # ... outros campos ...
        voz_run_name="voz_anime_v1",  # Checkpoint específico
    ),
    "curiosidades": ConfigNicho(
        nome="curiosidades",
        # ... outros campos ...
        voz_run_name="voz_documentario_v1",
    ),
    "filmes": ConfigNicho(
        nome="filmes",
        # ... outros campos ...
        voz_run_name="voz_cinematica_v1",
    ),
}
```

### 3. Estender Glossário Fonético (Opcional)

Edite `services/audio/glossario_fonetico.py`:

```python
GLOSSARIO_FONETICO = {
    # ... termos existentes ...
    
    # Adicione seus termos:
    "Skyrim": "Skírim",
    "Minecraft": "Máinecraft",
    "Roblox": "Róblox",
}
```

Ou adicione programaticamente:

```python
from services.audio.glossario_fonetico import adicionar_termo

adicionar_termo("SeuTermo", "Pronúncia Correta")
```

---

## Teste de Integração

### 1. Teste Básico

```bash
# Executar testes unitários
python -m pytest tests/test_voice_pipeline_client.py -v

# Esperado: 9 passed, 1 skipped
```

### 2. Teste com Serviço Real

```python
# teste_manual.py
import asyncio
from pathlib import Path
from services.audio.voice_pipeline_client import get_voice_pipeline_client

async def testar():
    client = get_voice_pipeline_client()
    
    # Healthcheck
    saudavel = await client.healthcheck()
    print(f"✅ Serviço saudável: {saudavel}")
    
    if saudavel:
        # Gerar áudio de teste
        audio_path, tempo = await client.narrar(
            texto="Este é um teste do novo pipeline de voz.",
            run_name="minha_voz_v1",
        )
        print(f"✅ Áudio gerado: {audio_path}")
        print(f"   Tempo: {tempo:.2f}s")
        print(f"   Tamanho: {audio_path.stat().st_size} bytes")

asyncio.run(testar())
```

### 3. Teste End-to-End

```bash
# Processar um vídeo de teste
python main.py --video-id TEST_001 --fase-inicio 3 --nicho animes
```

---

## Monitoramento

### Logs Estruturados

```python
# Exemplo de log de sucesso
{
    "level": "INFO",
    "message": "voice_pipeline.concluido",
    "tempo_sintese": 32.5,
    "tentativas": 1,
    "run_name": "minha_voz_v1"
}

# Exemplo de log de retry
{
    "level": "WARNING",
    "message": "voice_pipeline.gpu_ocupada_retry",
    "attempt": 2,
    "max_retries": 3,
    "retry_delay": 2.0
}
```

### Métricas Importantes

- **Latência de síntese:** tempo entre requisição e resposta
- **Taxa de retry 409:** indica contenção de GPU
- **Taxa de erro 500:** indica problemas no serviço
- **WER médio:** qualidade da síntese

---

## Troubleshooting

### Problema: Serviço indisponível

**Sintoma:** Healthcheck retorna `False` ou timeout

**Soluções:**
1. Verificar se containers estão rodando: `docker ps`
2. Verificar logs do orchestrator: `docker logs orchestrator`
3. Verificar conectividade: `curl http://localhost:9000/health`

---

### Problema: run_name inválido

**Sintoma:** Erro 400 "run_name não encontrado"

**Soluções:**
1. Verificar se checkpoint existe: `ls data/checkpoints/<run_name>.yml`
2. Verificar se arquivo de config está correto
3. Usar run_name existente ou treinar novo checkpoint

---

### Problema: GPU ocupada (409 frequente)

**Sintoma:** Muitos retries com código 409

**Soluções:**
1. Reduzir concorrência no media-assemble
2. Aumentar `VOICE_PIPELINE_MAX_RETRIES`
3. Aumentar `VOICE_PIPELINE_RETRY_DELAY`
4. Considerar serializar chamadas de áudio

---

### Problema: WER alto após síntese

**Sintoma:** `wer_final > 0.15` frequentemente

**Soluções:**
1. Adicionar termos problemáticos ao glossário fonético
2. Verificar qualidade do checkpoint treinado
3. Ajustar limite de WER: `WER_LIMITE_APROVACAO=0.20`
4. Aumentar tentativas: `MAX_TENTATIVAS_TTS=5`

---

### Problema: Timeout frequente

**Sintoma:** Erro "Timeout após 300s"

**Soluções:**
1. Aumentar timeout: `VOICE_PIPELINE_TIMEOUT=600`
2. Verificar saúde da GPU (pode estar lenta)
3. Reduzir carga no servidor de voz
4. Verificar logs do Seed-VC

---

## Checklist de Deploy

### Pré-Deploy

- [ ] Servidor de voz rodando e saudável
- [ ] Checkpoints treinados disponíveis
- [ ] Variáveis de ambiente configuradas
- [ ] Testes unitários passando
- [ ] Glossário fonético revisado

### Deploy

- [ ] Atualizar código do media-assemble
- [ ] Reiniciar serviços (se aplicável)
- [ ] Executar teste de integração
- [ ] Processar vídeo de teste

### Pós-Deploy

- [ ] Monitorar logs por 1 hora
- [ ] Verificar métricas de latência
- [ ] Verificar taxa de erro
- [ ] Documentar problemas encontrados

---

## Rollback

Se necessário reverter para F5-TTS:

```bash
# 1. Restaurar pipeline original
cp services/audio/pipeline_audio_f5tts_backup.py services/audio/pipeline_audio.py

# 2. Reverter configurações
git checkout pipeline/config.py pipeline/nichos.py pipeline/schemas.py

# 3. Reinstalar F5-TTS
pip install git+https://github.com/SWivid/F5-TTS.git

# 4. Configurar .env
F5_TTS_REF_AUDIO=data/voz_referencia/minha_voz.wav
F5_TTS_REF_TEXT="Texto de referência para clonagem"

# 5. Testar
python -m pytest tests/test_audio_pipeline.py -v
```

---

## Suporte

Para problemas ou dúvidas:

1. Consulte o `RELATORIO_REFATORACAO_AUDIO.md`
2. Verifique os logs estruturados
3. Execute testes de integração
4. Contate o time de desenvolvimento

---

**Última atualização:** 2026-08-11  
**Versão:** 1.0
