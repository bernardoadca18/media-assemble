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

### Passos

1. **Instale dependências**
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure .env**
   ```bash
   cp .env.example .env
   # Edite com suas credenciais locais
   ```

3. **Execute migrations**
   ```bash
   # Criar tabelas no banco
   psql -d faceless_pipeline -f db/migrations/versions/001_initial_schema.py
   ```

4. **Execute o pipeline**
   ```bash
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
