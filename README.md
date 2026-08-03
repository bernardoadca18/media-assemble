# Faceless Pipeline

Sistema modular para geração autônoma de vídeos "faceless" para YouTube. Arquitetura 100% Python, otimizada para execução local com GPU única (RTX 2060, 12GB VRAM).

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# ou .venv\Scripts\activate no Windows

pip install -r requirements.txt
cp .env.example .env  # preencher credenciais
```

### Banco de dados (PostgreSQL + Alembic)

```bash
createdb faceless_pipeline
```

Configure no `.env`:
```
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/faceless_pipeline
```

Rode as migrations:
```bash
alembic upgrade head
```

Isso cria o schema `dados` e as tabelas `videos_ideias`, `roteiros` e `execucoes_pipeline`.

## Uso

### Pipeline completo (Fase 1 + Fase 2)

```bash
python main.py --run-once
```

Este comando executa:
1. Coleta tendências do Google Trends
2. Normaliza via LLM
3. Gera 5 ideias de vídeo
4. Seleciona a melhor ideia
5. Gera roteiro completo em JSON
6. Persiste roteiro no banco

### Apenas Fase 1 (ideação)

```bash
python -m pipeline.orchestrator
```

### Testes

```bash
pytest -v
```

Todos os 32 testes devem passar.

## Arquitetura

```
pipeline/       # Orquestração, configuração e schemas (fonte da verdade)
services/       # Um módulo por etapa (trends, ideation, scripting, audio, visual, render)
db/             # Modelos SQLAlchemy e acesso a dados
utils/          # Logging estruturado e cliente LiteLLM
remotion/       # Projeto Node.js/React (Fase 5)
data/           # Assets locais, áudio temporário, saída final
tests/          # Testes automatizados
```

### Princípio de concorrência

Toda chamada que toca a GPU local (LLM local via LiteLLM, F5-TTS, Faster-Whisper) **deve** passar pelo `gpu_task` de `pipeline/gpu_lock.py`. Chamadas a modelos em nuvem (Claude, Gemini, OpenAI) não precisam desse lock.

## Status das fases

| Fase | Escopo | Status |
|---|---|---|
| 1 | Tendências + Ideação | Implementado |
| 2 | Roteirização completa | Implementado |
| 3 | Áudio (F5-TTS + Whisper + WER) | Stub |
| 4 | Assets visuais | Stub |
| 5 | Renderização (Remotion) | Stub |
| 6 | Orquestração end-to-end + observabilidade | Não iniciado |
| 7 | Hardening, multi-nicho, deploy | Não iniciado |

Ver `RELATORIO_FASES_DESENVOLVIMENTO.md` para detalhes de cada fase.

## Fase 2: Roteirização

### Persistência

Roteiros são persistidos na tabela `dados.roteiros` no PostgreSQL.

**Vantagens:**
- Consultas SQL diretas para análise e debugging
- Versionamento via campo `criado_em`
- Backup integrado com o restante do projeto

### Schema do roteiro

O schema `Roteiro` em `pipeline/schemas.py` é a fonte da verdade. O agente de roteirização:
- Valida resposta do LLM contra o schema Pydantic
- Aplica regras de negócio (duração de cenas, animações, texto destaque)
- Realiza retry com correção em caso de falha de validação

### Regras de negócio validadas

- Mínimo de 10 cenas por roteiro
- Duração de cena: 3-8 segundos
- Animações não podem repetir 3x consecutivas
- Texto destaque em no máximo 1/3 das cenas
