# 🔍 Diagnóstico do Erro - Fase 3 (Áudio)

**Data:** 2026-08-10 02:08 UTC
**Status:** ❌ BLOQUEADO - F5-TTS não instalado

---

## 📊 Progresso do Pipeline

### ✅ Fases Concluídas com Sucesso

**Fase 1 - Trends + Ideação:**
- ✅ Coleta de trends via Reddit RSS
- ❌ Google Trends bloqueado (esperado)
- ✅ YouTube trending coletado
- ✅ 5 ideias geradas via `gemini-3.6-flash`

**Fase 2 - Roteirização:**
- ✅ Roteiro gerado via `gemini-3.5-flash-lite`
- ✅ Schema JSON validado
- ✅ `video_id` gerado: `20110478`

### ❌ Fase 3 - Áudio (FALHOU)

**Erro:**
```
ModuleNotFoundError: No module named 'f5_tts_infer'
RuntimeError: Não foi possível gerar áudio para cena 1
```

---

## 🐛 Análise do Problema

### Causa Raiz
O módulo **F5-TTS não está instalado** no ambiente Python. O `requirements.txt` contém um comentário:
```python
# f5-tts  # instalar conforme instruções do repositório oficial (não está no PyPI padrão)
```

### Por que não está no PyPI?
F5-TTS é um projeto de pesquisa ativo que:
1. Não tem release estável no PyPI
2. Requer instalação via Git
3. Tem dependências específicas de GPU (CUDA)

---

## 🔧 Soluções

### Opção A: Instalar F5-TTS (RECOMENDADO para usar TTS real)

```bash
# 1. Clonar repositório
cd /tmp
git clone https://github.com/SWivid/F5-TTS.git
cd F5-TTS

# 2. Instalar dependências
pip install -e .

# 3. Verificar instalação
python -c "from f5_tts.api import F5TTS; print('✅ F5-TTS instalado')"
```

**Pré-requisitos:**
- CUDA 11.8+ (para GPU)
- PyTorch com suporte CUDA
- ~4GB VRAM disponível

### Opção B: Usar TTS Alternativo (edge-tts - GRATUITO)

**Vantagens:**
- Disponível no PyPI
- Não requer GPU
- Vozes de alta qualidade (Microsoft Edge)
- Totalmente gratuito

**Instalação:**
```bash
pip install edge-tts
```

**Modificação necessária em `services/audio/tts_engine.py`:**
```python
# Substituir F5-TTS por edge-tts
import edge_tts

async def gerar_audio_cena(texto: str, saida: Path, seed: int | None = None) -> Path:
    communicate = edge_tts.Communicate(texto, "pt-BR-AntonioNeural")
    await communicate.save(str(saida))
    return saida
```

### Opção C: Pular Fase de Áudio (TESTE APENAS)

**Para testar pipeline completo:**
```python
# Em pipeline/orchestrator.py:302
# Comentar temporariamente:
# roteiro = await gerar_audio_do_roteiro(roteiro)

# Adicionar áudio dummy
for cena in roteiro.cenas:
    cena.audio_path = "data/audio_dummy/placeholder.wav"
```

---

## ⚠️ Problemas Adicionais Identificados

### 1. Modelo Local `qwen-local` Falhando
```
{"level": "ERROR", "message": "litellm.erro_permanente_local"}
```

**Causa:** Código tentou usar modelo local para normalização de trends, mas LiteLLM não estava passando credenciais.

**Status:** Verificar se `local_model_base_url` está correto para execução local (não Docker).

### 2. Embeddings com Erros
```
{"level": "ERROR", "message": "checar_duplicidade_semantica.erro"}
```

**Causa:** Embeddings não foram gerados para verificar duplicidade semântica das ideias.

**Impacto:** Pipeline continuou, mas sem verificação de duplicidade.

### 3. Roteiro Falhou na Primeira Tentativa
```
{"level": "WARNING", "message": "gerar_roteiro.regras_negocio_falharam"}
```

**Causa:** Modelo `gemini-3.5-flash-lite` gerou roteiro inválido na primeira tentativa.

**Status:** Retry automático funcionou - roteiro gerado com sucesso na segunda tentativa.

---

## 📋 Checklist de Pré-requisitos para Fase 3

### Para F5-TTS:
- [ ] CUDA instalado e funcionando
- [ ] PyTorch com suporte CUDA
- [ ] Arquivo de voz de referência: `data/voz_referencia/audio_ref.wav`
- [ ] Texto de referência configurado no `.env`

### Para edge-tts (alternativa):
- [ ] Instalar: `pip install edge-tts`
- [ ] Modificar `services/audio/tts_engine.py`
- [ ] Testar geração de áudio

### Validação:
```bash
# Verificar voz de referência
ls -la data/voz_referencia/audio_ref.wav

# Se não existir, criar placeholder
mkdir -p data/voz_referencia
# Colocar arquivo de áudio de referência (5-10 segundos)
```

---

## 🎯 Recomendação Imediata

### Solução Rápida: edge-tts

**Vantagens:**
1. Instalação simples: `pip install edge-tts`
2. Não requer GPU
3. Funciona imediatamente
4. Vozes naturais em português

**Implementação:**

```bash
# 1. Instalar
pip install edge-tts

# 2. Testar
edge-tts --list-voices | grep pt-BR

# 3. Modificar tts_engine.py (vou criar versão adaptada)
```

---

## 📝 Próximos Passos

1. **Escolher solução de TTS** (F5-TTS ou edge-tts)
2. **Instalar dependências**
3. **Configurar voz de referência** (se F5-TTS)
4. **Testar geração de áudio isoladamente**
5. **Re-executar pipeline completo**

---

## 🔗 Referências

- [F5-TTS GitHub](https://github.com/SWivid/F5-TTS)
- [edge-tts PyPI](https://pypi.org/project/edge-tts/)
- [Faster-Whisper Documentation](https://github.com/guillaumekln/faster-whisper)

---

**Status Atual do Pipeline:**
- ✅ Fases 1 e 2 funcionando
- ❌ Fase 3 bloqueada por F5-TTS
- ⏸️ Fases 4, 5, 6 não testadas

**Tempo até falha:** ~60 segundos
**Custo estimado:** ~$0.0005 (2 chamadas LLM)
