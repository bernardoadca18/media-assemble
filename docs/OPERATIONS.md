# Runbook de Operação — Faceless Pipeline

Este documento cobre os procedimentos operacionais para manter e expandir o pipeline de geração de vídeos faceless.

---

## 1. Ingestão de Gameplay Footage

### 1.1 Adicionar novo footage de gameplay

O pipeline aceita vídeos brutos de gameplay para segmentação automática.

**Passos:**

1. **Preparar o vídeo bruto**
   - Formato aceito: MP4, WebM, MOV
   - Duração recomendada: 10-60 minutos por arquivo
   - Resolução preferencial: 1920x1080 (1080p)

2. **Copiar para o diretório de ingestão**
   ```bash
   cp meu_gameplay.mp4 data/gameplay_raw/
   ```

3. **Executar ingestão manual** (ou aguardar processamento agendado)
   ```bash
   python -m services.gameplay.ingestion
   ```

4. **Verificar segmentos gerados**
   ```bash
   ls data/gameplay_processed/
   ```

**Parâmetros configuráveis (`.env`):**
- `GAMEPLAY_SEGMENT_DURATION_SEC=30` — Duração de cada segmento
- `GAMEPLAY_MIN_MOTION_SCORE=5.0` — Score mínimo de movimento para aprovar segmento

**Troubleshooting:**
- **Segmentos rejeitados**: Aumente `GAMEPLAY_MIN_MOTION_SCORE` se muitos segmentos estiverem muito estáticos
- **Erro de codec**: Verifique se ffmpeg está instalado (`ffmpeg -version`)

### 1.2 Verificar qualidade dos segmentos

Após ingestão, revise amostralmente os segmentos:

```bash
# Listar segmentos aprovados
ls data/gameplay_processed/aprovados/

# Reproduzir um segmento para verificação
ffplay data/gameplay_processed/aprovados/segmento_001.mp4
```

---

## 2. Adicionar Novo Canal em Modo Gameplay

### 2.1 Criar perfil de timbre

Cada canal deve ter um timbre de voz distinto para evitar repetição.

**Passos:**

1. **Escolher estratégia de timbre:**
   - **Determinístico (padrão):** O sistema calcula automaticamente pitch e velocidade baseado no `canal_id`
   - **Manual override:** Configurar valores específicos no nicho

2. **Para override manual, editar `pipeline/nichos.py`:**
   ```python
   ConfigNicho(
       nome="meu_nicho",
       # ... outros campos ...
       pitch_shift_semitons=1.5,  # -2.0 a +2.0
       velocidade_fala=0.97,      # 0.95 a 1.05
   )
   ```

3. **Testar o perfil:**
   ```python
   from services.gameplay.crop_config import obter_crop_offset_y
   from services.audio.timbre_variation import calcular_variacao_canal

   # Verificar valores determinísticos
   pitch, vel = calcular_variacao_canal("meu_novo_canal")
   print(f"Pitch: {pitch}, Velocidade: {vel}")
   ```

### 2.2 Configurar crop vertical por jogo

Se o canal usa um jogo específico, configure o crop vertical:

1. **Verificar se o jogo já tem configuração:**
   ```python
   from services.gameplay.crop_config import obter_crop_offset_y, listar_jogos_configurados

   print(listar_jogos_configurados())
   ```

2. **Adicionar novo jogo (se necessário):**

   Editar `services/gameplay/crop_config.py`:
   ```python
   CROP_CONFIG_POR_JOGO["novo_jogo"] = CropConfigJogo(
       jogo="novo_jogo",
       crop_offset_y=50,  # Ajuste baseado na HUD
       descricao="Descrição do enquadramento",
   )
   ```

3. **Testar o crop:**
   - Gerar um vídeo de teste
   - Verificar se a ação principal está visível
   - Ajustar offset se necessário (negativo = move para cima, positivo = move para baixo)

### 2.3 Configurar intensidade de gameplay

Cada nicho pode preferir intensidades diferentes:

```python
ConfigNicho(
    nome="meu_nicho",
    # ... outros campos ...
    gameplay_intensidade_preferida="intenso",  # "leve", "moderado", "intenso"
)
```

---

## 3. Publicação Cruzada YouTube + TikTok

### 3.1 Checklist de publicação

Quando o vídeo estiver pronto para publicação:

**YouTube (vídeo longo):**

- [ ] Baixar vídeo de `data/output_final/{video_id}.mp4`
- [ ] Baixar metadata de `data/output_final/{video_id}_metadata.json`
- [ ] Verificar título e descrição
- [ ] Confirmar tags relevantes
- [ ] Adicionar miniatura personalizada (opcional)
- [ ] Publicar como "Não listado" primeiro para revisão
- [ ] Após aprovação, mudar para "Público"

**TikTok (Short):**

- [ ] Baixar Short de `data/output_final/{video_id}_clip_*.mp4`
- [ ] Verificar legenda inicial (gancho)
- [ ] Confirmar formato vertical (9:16)
- [ ] Publicar com hashtags relevantes
- [ ] Cross-post para Instagram Reels (opcional)

### 3.2 Fluxo de reaproveitamento

O mesmo Short vertical pode ser publicado em múltiplas plataformas:

```
Pipeline gera Short (1080x1920)
         ↓
   ┌─────┴─────┐
   ↓           ↓
TikTok    Instagram Reels
```

**Nota:** O pipeline NÃO faz upload automático. Publicação é sempre manual.

---

## 4. Atribuição de Imagem (Unsplash)

### 4.1 Verificar obrigatoriedade de atribuição

Quando um vídeo usa asset do Unsplash (fallback externo):

1. **Verificar origem do asset:**
   ```bash
   # No banco de dados ou log
   grep "asset_origem.*unsplash" logs/pipeline.log
   ```

2. **Localizar informações de atribuição:**
   - O asset salvo em `data/assets_local/` contém metadata de origem
   - Nome do arquivo inclui ID do Unsplash

3. **Adicionar atribuição na descrição:**
   ```
   Descrição do vídeo...

   ---
   Créditos das imagens:
   - [Descrição] por [Nome do Fotógrafo] no Unsplash
   ```

### 4.2 Checklist de atribuição

- [ ] Verificar se vídeo usou fallback externo
- [ ] Confirmar se asset veio do Unsplash
- [ ] Localizar nome do fotógrafo
- [ ] Adicionar linha de atribuição na descrição do YouTube
- [ ] Adicionar atribuição nos créditos do TikTok (se aplicável)

### 4.3 Formato de atribuição obrigatório

```
Imagens por:
- [Nome] no Unsplash (https://unsplash.com/@username)
```

**Importante:** A licença Unsplash exige atribuição para uso comercial.

---

## 5. Monitoramento e Saúde do Sistema

### 5.1 Verificar saúde do banco de dados

```bash
# Conectar ao banco
psql -d faceless_pipeline

# Verificar vídeos processados
SELECT COUNT(*) FROM videos WHERE status = 'concluido';

# Verificar segmentos de gameplay
SELECT jogo_origem, COUNT(*) FROM gameplay_segmentos GROUP BY jogo_origem;
```

### 5.2 Verificar fila de processamento

```bash
# Verificar próximos vídeos agendados
python -c "from pipeline.orchestrator import listar_videos_pendentes; print(listar_videos_pendentes())"
```

### 5.3 Logs importantes

- **Logs gerais:** `logs/pipeline.log`
- **Logs de áudio:** Verificar WER médio por vídeo
- **Logs de render:** Verificar tempo de renderização

### 5.4 Métricas de performance

Monitorar regularmente:

- **WER médio:** Deve ser < 5% para aprovação automática
- **Tempo de renderização:** Documentar por estilo visual
- **Taxa de revisão manual:** Percentual de vídeos que requerem intervenção

---

## 6. Troubleshooting Comum

### 6.1 Vídeo com WER alto

**Sintoma:** Vídeo marcado para revisão manual com WER > 5%

**Soluções:**
1. Verificar qualidade do áudio de referência
2. Ajustar parâmetros do F5-TTS
3. Regenerar áudio com seed diferente
4. Revisar texto de locução (pode ter pronúncias difíceis)

### 6.2 Segmento de gameplay rejeitado

**Sintoma:** Poucos segmentos aprovados após ingestão

**Soluções:**
1. Reduzir `GAMEPLAY_MIN_MOTION_SCORE` no `.env`
2. Verificar se o gameplay tem movimento suficiente
3. Confirmar que o vídeo não está corrompido

### 6.3 Crop vertical incorreto

**Sintoma:** HUD cortando ação importante

**Solução:**
1. Ajustar `crop_offset_y` em `services/gameplay/crop_config.py`
2. Testar com vídeo de exemplo
3. Documentar novo valor para o jogo

### 6.4 Erro de GPU

**Sintoma:** Whisper ou F5-TTS falhando com erro de CUDA

**Soluções:**
1. Verificar se GPU está disponível: `nvidia-smi`
2. Verificar lock de GPU: `data/gpu.lock`
3. Aguardar liberação ou remover lock órfão

---

## 7. Procedimentos de Backup

### 7.1 Backup do banco de dados

```bash
# Backup completo
pg_dump faceless_pipeline > backup_$(date +%Y%m%d).sql

# Restaurar
psql faceless_pipeline < backup_20260101.sql
```

### 7.2 Backup de assets

```bash
# Backup de gameplay bruto (NÃO descartar após processamento)
tar -czf gameplay_raw_backup.tar.gz data/gameplay_raw/

# Backup de voz de referência
tar -czf voz_referencia_backup.tar.gz data/voz_referencia/
```

---

## 8. Escalonamento e Expansão

### 8.1 Adicionar novo nicho

1. Editar `pipeline/nichos.py`
2. Adicionar nova entrada em `NICHOS_CONFIG`
3. Configurar prompts específicos
4. Testar com vídeo de exemplo
5. Atualizar `.env` com `NICHOS_ATIVOS`

### 8.2 Adicionar nova fonte de tendências

1. Editar `services/trends/rss_sources.py`
2. Adicionar nova fonte RSS
3. Testar coleta: `python -m services.trends.rss_sources`
4. Documentar fonte em `docs/TENDENCIES.md`

---

## 9. Contatos e Escalação

**Problemas de infraestrutura:** Verificar logs e reiniciar serviços

**Problemas de qualidade:** Revisar parâmetros de configuração

**Problemas de licença:** Revisar origem dos assets e atribuições

**Novas features:** Documentar requisito e avaliar impacto

---

## 10. Referências Rápidas

### Comandos úteis

```bash
# Executar pipeline uma vez
python main.py --run-once

# Verificar status
python main.py --status

# Executar testes
pytest tests/

# Verificar tipos TypeScript
cd remotion && npx tsc --noEmit
```

### Arquivos de configuração

- `.env` — Configurações de ambiente
- `pipeline/config.py` — Configurações do pipeline
- `pipeline/nichos.py` — Configurações por nicho
- `services/gameplay/crop_config.py` — Crop por jogo

### Limites e thresholds

- WER máximo para aprovação: 5%
- Duração de Short: 25-58 segundos
- Pitch shift: -2.0 a +2.0 semitons
- Velocidade: 0.95 a 1.05
- Crop offset Y: -500 a +500 pixels
