# Docker Configuration

## Visão Geral

Este projeto utiliza Docker Compose para orquestrar todos os serviços necessários:

- **postgres**: Banco de dados PostgreSQL (porta 5433)
- **api**: Backend FastAPI (porta 8080)
- **frontend**: Frontend React + Vite (porta 5173)
- **pipeline**: Worker de background para processamento

## Início Rápido

```bash
# 1. Copiar arquivo de ambiente
cp .env.example .env

# 2. Editar .env com suas credenciais
nano .env

# 3. Iniciar todos os serviços
docker compose up -d

# 4. Verificar status
docker compose ps

# 5. Ver logs
docker compose logs -f
```

## Acessos

| Serviço    | URL                          | Descrição                |
|------------|------------------------------|--------------------------|
| Frontend   | http://127.0.0.1:5173        | Interface web            |
| API        | http://127.0.0.1:8080        | Backend REST API         |
| API Docs   | http://127.0.0.1:8080/docs   | Documentação Swagger     |
| PostgreSQL | localhost:5433               | Banco de dados           |

## Comandos Úteis

```bash
# Iniciar serviços específicos
docker compose up -d postgres api frontend

# Parar todos os serviços
docker compose down

# Parar e remover volumes
docker compose down -v

# Reconstruir imagens
docker compose build --no-cache

# Ver logs de um serviço específico
docker compose logs -f api

# Executar comando em container
docker compose exec api bash

# Reiniciar um serviço
docker compose restart api
```

## Desenvolvimento

### Backend (desenvolvimento local)

```bash
# Rodar apenas o banco de dados
docker compose up -d postgres

# Rodar API localmente
python scripts/start_api.py --reload

# Rodar pipeline localmente
python main.py
```

### Frontend (desenvolvimento local)

```bash
# Rodar apenas o banco e a API
docker compose up -d postgres api

# Rodar frontend em modo dev
cd frontend
npm install
npm run dev
```

## Variáveis de Ambiente

### Banco de Dados

- `POSTGRES_USER`: Usuário do PostgreSQL
- `POSTGRES_PASSWORD`: Senha do PostgreSQL
- `POSTGRES_DB`: Nome do banco de dados
- `POSTGRES_PORT`: Porta externa (padrão: 5433)

### LiteLLM / Modelos

- `LITELLM_MASTER_KEY`: Chave de autenticação do proxy LiteLLM
- `LITELLM_BASE_URL`: URL do proxy LiteLLM (dentro do container usar `host.docker.internal:4000`)
- `LOCAL_MODEL_NAME`: Nome do modelo local (ex: qwen-local)
- `CLOUD_MODEL_IDEACAO`: Modelo para ideação (ex: gemini-3.6-flash)
- `CLOUD_MODEL_ROTEIRO`: Modelo para roteiros (ex: gemini-3.1-pro)

### Frontend

- `VITE_API_URL`: URL da API backend (padrão: http://127.0.0.1:8080)

## Redes e Comunicação

Todos os serviços estão conectados à rede `faceless-network`. Dentro dos containers, use os nomes dos serviços como hostnames:

- `postgres`: Banco de dados
- `api`: Backend API
- `frontend`: Frontend
- `pipeline`: Worker de background

### Comunicação Container → Host

Para acessar serviços rodando no host (como LiteLLM), use:
- `host.docker.internal:porta` (Linux/Mac)
- IP do host no Windows

## Saúde dos Serviços

Todos os serviços possuem health checks configurados:

```bash
# Verificar saúde
docker compose ps

# Ver detalhes do health check
docker inspect faceless_api --format='{{json .State.Health}}' | jq
```

## Troubleshooting

### Porta já em uso

```bash
# Verificar qual processo está usando a porta
ss -tlnp | grep :5433

# Matar processo se necessário
kill -9 <PID>
```

### Container não inicia

```bash
# Ver logs detalhados
docker compose logs api

# Verificar configuração
docker compose config

# Reconstruir imagem
docker compose build --no-cache api
docker compose up -d api
```

### Problemas de permissão

```bash
# Corrigir permissões de volumes
sudo chown -R $USER:$USER data logs
```

### GPU não detectada

```bash
# Verificar se NVIDIA Container Toolkit está instalado
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi

# Se falhar, instale o toolkit:
# Ubuntu: sudo apt-get install -y nvidia-container-toolkit
```

## Produção

Para ambiente de produção, considere:

1. **Variáveis de ambiente**: Use um gerenciador de secrets
2. **HTTPS**: Configure certificados SSL/TLS
3. **Autenticação**: Implemente autenticação na API
4. **Backup**: Configure backup automático do PostgreSQL
5. **Monitoramento**: Adicione Prometheus/Grafana
6. **Logs**: Configure centralização de logs (ELK, Loki)

### Exemplo com Traefik (HTTPS)

```yaml
services:
  api:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.api.rule=Host(`api.seudominio.com`)"
      - "traefik.http.routers.api.tls.certresolver=letsencrypt"

  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`app.seudominio.com`)"
      - "traefik.http.routers.frontend.tls.certresolver=letsencrypt"
```
