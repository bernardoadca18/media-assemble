FROM python:3.11-slim

# Evita prompts interativos durante instalação de pacotes
ENV DEBIAN_FRONTEND=noninteractive

# Instala dependências do sistema (ffmpeg para áudio/vídeo, build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Cria diretório de trabalho
WORKDIR /app

# Copia arquivos de dependências
COPY requirements.txt .

# Instala dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# Copia código do projeto
COPY . .

# Cria diretórios de dados
RUN mkdir -p data/audio_gerado data/assets_local data/voz_referencia logs

# Variáveis de ambiente padrão
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=postgresql+asyncpg://usuario:senha@postgres:5432/faceless_pipeline

# Comando padrão (scheduler)
CMD ["python", "main.py"]
