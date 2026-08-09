# Deploy do Faceless Pipeline

## Opção 1: Docker Compose (Recomendado)

### Pré-requisitos
- Docker 20.10+
- Docker Compose 2.0+
- (Opcional) NVIDIA Container Toolkit para GPU

### Passos

1. **Clone o repositório**
   ```bash
   git clone https://github.com/seu-usuario/faceless-pipeline.git
   cd faceless-pipeline
   ```

2. **Configure variáveis de ambiente**
   ```bash
   cp .env.example .env
   # Edite .env com suas credenciais
   ```

3. **Inicie os serviços**
   ```bash
   docker-compose up -d
   ```

4. **Verifique logs**
   ```bash
   docker-compose logs -f pipeline
   ```

### Comandos úteis

```bash
# Parar serviços
docker-compose down

# Reiniciar pipeline
docker-compose restart pipeline

# Executar uma vez (sem scheduler)
docker-compose run --rm pipeline python main.py --run-once

# Listar execuções falhas
docker-compose run --rm pipeline python main.py --listar-falhas

# Retomar execução falha
docker-compose run --rm pipeline python main.py --retomar VIDEO_ID
```

### GPU Support

Para usar GPU (Whisper, TTS), descomente a seção `deploy` no `docker-compose.yml` e instale o [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

---

## Opção 2: Systemd (Linux nativo)

### Pré-requisitos
- Python 3.11+
- PostgreSQL 15+
- FFmpeg
- (Opcional) CUDA para GPU

### Passos

1. **Crie usuário do sistema**
   ```bash
   sudo useradd -r -s /bin/bash -m -d /opt/faceless-pipeline faceless
   ```

2. **Clone e instale dependências**
   ```bash
   sudo -u faceless -H bash -c "
       cd /opt/faceless-pipeline
       git clone https://github.com/seu-usuario/faceless-pipeline.git .
       python3.11 -m venv .venv
       .venv/bin/pip install -r requirements.txt
   "
   ```

3. **Configure variáveis de ambiente**
   ```bash
   sudo -u faceless cp /opt/faceless-pipeline/.env.example /opt/faceless-pipeline/.env
   sudo -u faceless nano /opt/faceless-pipeline/.env
   ```

4. **Instale serviço systemd**
   ```bash
   sudo cp /opt/faceless-pipeline/faceless-pipeline.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable faceless-pipeline
   sudo systemctl start faceless-pipeline
   ```

5. **Verifique status**
   ```bash
   sudo systemctl status faceless-pipeline
   sudo journalctl -u faceless-pipeline -f
   ```

### Comandos úteis

```bash
# Ver logs em tempo real
sudo journalctl -u faceless-pipeline -f

# Reiniciar serviço
sudo systemctl restart faceless-pipeline

# Parar serviço
sudo systemctl stop faceless-pipeline

# Executar uma vez manualmente
sudo -u faceless -H bash -c "
    cd /opt/faceless-pipeline
    .venv/bin/python main.py --run-once
"
```

---

## Opção 3: Desenvolvimento Local

### Pré-requisitos
- Python 3.11+
- PostgreSQL 15+ (ou usar Docker apenas para o banco)
- FFmpeg
- Node.js 18+ (para frontend e Remotion)

### Passos

1. **Instale dependências Python**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Instale dependências Node.js**
   ```bash
   # Frontend
   cd frontend && npm install && cd ..

   # Remotion (renderização)
   cd remotion && npm install && cd ..
   ```

3. **Configure .env**
   ```bash
   cp .env.example .env
   # Edite com suas credenciais locais
   ```

4. **Execute migrations**
   ```bash
   # Criar tabelas no banco
   psql -d faceless_pipeline -f db/migrations/versions/001_initial_schema.py
   ```

5. **Inicie a API (backend para frontend)**
   ```bash
   # Terminal 1: API FastAPI
   uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
   ```

6. **Inicie o frontend (opcional)**
   ```bash
   # Terminal 2: Frontend React
   cd frontend && npm run dev
   # Acesse http://localhost:5173
   ```

7. **Execute o pipeline**
   ```bash
   # Terminal 3: Pipeline
   # Modo scheduler
   python main.py

   # Executar uma vez
   python main.py --run-once

   # Listar falhas
   python main.py --listar-falhas

   # Retomar execução
   python main.py --retomar VIDEO_ID
   ```

---

## Monitoramento

### Health Checks

- **PostgreSQL**: `docker-compose exec postgres pg_isready`
- **Pipeline**: Verificar se o processo está rodando (`docker ps` ou `systemctl status`)

### Logs

- **Docker**: `docker-compose logs -f pipeline`
- **Systemd**: `journalctl -u faceless-pipeline -f`
- **Arquivos**: `tail -f logs/pipeline.log`

### Métricas (futuro)

Considerar integrar com:
- Prometheus + Grafana para métricas
- Sentry para erros
- ELK Stack para logs centralizados

---

## Backup

### Banco de dados

```bash
# Backup
docker-compose exec postgres pg_dump -U faceless faceless_pipeline > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260101.sql | docker-compose exec -T postgres psql -U faceless faceless_pipeline
```

### Dados (áudio, vídeos, assets)

```bash
# Backup
tar -czvf data_backup_$(date +%Y%m%d).tar.gz data/ remotion/videos/

# Restore
tar -xzvf data_backup_20260101.tar.gz
```

---

## Troubleshooting

### Erro de conexão com banco

```bash
# Verifique se PostgreSQL está rodando
docker-compose ps postgres

# Verifique logs
docker-compose logs postgres
```

### Erro de GPU não detectada

```bash
# Verifique se NVIDIA driver está instalado
nvidia-smi

# Verifique NVIDIA Container Toolkit
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### Pipeline não gera vídeos

```bash
# Verifique logs
docker-compose logs pipeline | grep -i erro

# Execute manualmente para debug
docker-compose run --rm pipeline python main.py --run-once
```

### Whisper lento

- Use GPU: configure `WHISPER_DEVICE=cuda`
- Reduza tamanho do modelo: `WHISPER_MODEL_SIZE=small` ou `base`
- Use float16: `WHISPER_COMPUTE_TYPE=float16`

---

## Revisão Visual de Shorts com Gameplay (Fase 9.4)

### Visão geral

Quando o modo `gameplay_bg` é usado para Shorts/TikTok, vídeos de gameplay horizontais (16:9) são cropados verticalmente para o formato 9:16. O processo de revisão visual garante que o enquadramento está correto e que elementos importantes (HUD, ação) estão visíveis.

### Configuração de crop por jogo

Cada jogo pode ter um offset Y específico para ajustar o enquadramento:

| Jogo | Offset Y | Descrição |
|------|----------|-----------|
| Minecraft | 0 | Centrado |
| Fortnite | -50 | Acima (evitar HUD baixa) |
| Valorant | 100 | Abaixo (minimap no topo) |
| League of Legends | 150 | Mais abaixo (evitar minimap) |
| GTA V | -80 | Acima (minimap canto inferior) |
| Call of Duty | 0 | Centrado |
| Apex Legends | 50 | Abaixo (evitar HUD superior) |
| Dota 2 | 150 | Mais abaixo (minimap inferior) |
| CS:GO | 0 | Centrado |
| Free Fire | -30 | Acima (controles mobile) |

Para adicionar um novo jogo, edite `services/gameplay/crop_config.py`:

```python
CROP_CONFIG_POR_JOGO["novo_jogo"] = CropConfigJogo(
    jogo="novo_jogo",
    crop_offset_y=50,  # Ajuste baseado na HUD
    descricao="Descrição do enquadramento",
)
```

### Processo de revisão visual

1. **Gere um vídeo de teste**
   ```bash
   # Com o pipeline rodando, aguarde gerar um vídeo com gameplay_bg
   # Ou execute manualmente:
   python main.py --run-once --nicho cultura_pop
   ```

2. **Verifique o vídeo gerado**
   - Abra o vídeo em `data/output_final/`
   - Confira se a ação principal está visível
   - Verifique se a HUD não cobre conteúdo importante
   - Valide se o crop vertical está bem posicionado

3. **Ajuste o offset se necessário**
   - Se a HUD está cortando ação, ajuste `crop_offset_y` em `crop_config.py`
   - Valores negativos movem o crop para cima
   - Valores positivos movem o crop para baixo

4. **Teste novamente**
   ```bash
   # Regenere o vídeo com nova configuração
   python main.py --run-once
   ```

### Checklist de revisão

- [ ] HUD do jogo não cobre legenda
- [ ] Ação principal está visível no centro
- [ ] Personagens/objetos importantes não estão cortados
- [ ] Minimap não está em área importante (se aplicável)
- [ ] Transições entre cenas gameplay estão suaves
- [ ] Crossfade entre segmentos está correto

### Ajuste fino por canal

Se um canal específico precisa de ajuste diferente:

1. Edite `pipeline/nichos.py` para adicionar configuração específica
2. O campo `crop_offset_y` em `Cena` pode ser setado manualmente
3. Use `obter_crop_offset_y(jogo, default=valor)` para override

### Troubleshooting comum

**HUD cobrindo legenda:**
- Ajuste `crop_offset_y` para mover a área de interesse
- Verifique se `SubtitlesOverlay` está posicionado corretamente

**Ação cortada:**
- O offset pode precisar ser mais negativo (mover crop para cima)
- Verifique se o segmento de gameplay tem movimento suficiente

**Vídeo muito estático:**
- Verifique `gameplay_min_motion_score` nas configurações
- Segmentos com pouco movimento podem ser rejeitados automaticamente
