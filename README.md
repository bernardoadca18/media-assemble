# Faceless Pipeline — Sistema Autônomo de Vídeos (100% Python)

Sistema modular para geração autônoma de vídeos "faceless" para YouTube,
substituindo o fluxo n8n `Scrapper` por uma arquitetura 100% Python,
otimizada para execução local com GPU única (RTX 2060, 12GB VRAM).

Ver `RELATORIO_FASES_DESENVOLVIMENTO.md` para o plano de fases completo.
Este repositório contém a **base estrutural** do projeto — a Fase 1
(Tendências + Ideação) já está com uma implementação de referência;
as fases seguintes estão marcadas como `NotImplementedError` com
docstrings apontando o escopo e a seção correspondente do guia de
arquitetura original.

## Setup rápido

```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\\Scripts\\activate no Windows
pip install -r requirements.txt
cp .env.example .env        # preencher credenciais e paths reais
```

### Banco de dados (PostgreSQL + Alembic)

1. Crie o banco de dados:
```bash
createdb faceless_pipeline
```

2. Configure a `DATABASE_URL` no `.env`:
```
DATABASE_URL=postgresql+asyncpg://usuario:senha@localhost:5432/faceless_pipeline
```

3. Rode as migrations:
```bash
alembic upgrade head
```

Isso cria o schema `dados` e as tabelas `videos_ideias`, `roteiros` e `execucoes_pipeline`.

### Testes

Rode a suite de testes:
```bash
pytest -v
```

Todos os 32 testes devem passar.

## Rodando o pipeline

### Fase 1 + Fase 2 (ideação + roteirização)

```bash
python main.py --run-once
```

Este comando executa o pipeline ponta-a-ponta:
1. Coleta tendências do Google Trends
2. Normaliza via LLM local
3. Gera 5 ideias de vídeo
4. Seleciona a melhor ideia
5. Gera roteiro completo em JSON
6. Persiste roteiro no banco

### Fase 1 isoladamente

```bash
python -m pipeline.orchestrator
```

Ou, via entrypoint principal:

```bash
python main.py --run-once
```

## Estrutura de pastas

```
pipeline/       # Orquestração, configuração e schemas (fonte da verdade)
services/       # Um módulo por etapa do pipeline (trends, ideation,
                # scripting, audio, visual, render)
db/             # Modelos SQLAlchemy e acesso a dados
utils/          # Logging estruturado e cliente unificado LiteLLM
remotion/       # Projeto Node.js/React isolado (Fase 5)
data/           # Assets locais, áudio temporário, saída final
tests/          # Testes automatizados
```

## Princípio de concorrência (importante)

Toda chamada que toca a GPU local (LLM local via LiteLLM, F5-TTS,
Faster-Whisper) **deve** passar pelo `gpu_task` de `pipeline/gpu_lock.py`.
Chamadas a modelos em nuvem (Claude, Gemini, OpenAI) não precisam desse
lock e podem rodar em paralelo livremente.

## Status das fases

| Fase | Escopo | Status nesta base |
|---|---|---|
| 1 | Tendências + Ideação | Implementação de referência incluída |
| 2 | Roteirização completa | **Implementado** — gera roteiro JSON validado |
| 3 | Áudio (F5-TTS + Whisper + WER) | Stub (`NotImplementedError`) |
| 4 | Assets visuais | Stub (`NotImplementedError`) |
| 5 | Renderização (Remotion) | Stub (`NotImplementedError`) |
| 6 | Orquestração end-to-end + observabilidade | Não iniciado |
| 7 | Hardening, multi-nicho, deploy | Não iniciado |

## Decisões de arquitetura (Fase 2)

### Persistência de roteiros

Os roteiros gerados são persistidos na tabela `dados.roteiros` no PostgreSQL. Esta escolha foi feita por:

1. **Consistência**: Mesmo banco já usado para ideias e execuções
2. **Query simplicity**: Consultas SQL diretas para análise e debugging
3. **Versionamento**: O campo `criado_em` permite rastrear evolução de roteiros para o mesmo `video_id`
4. **Backup integrado**: Segue mesma estratégia de backup do restante do projeto

Alternativa considerada: armazenamento em disco como JSON em `data/roteiros/`. Descartada por adicionar complexidade de sincronização com o banco.

### Schema do roteiro

O schema `Roteiro` em `pipeline/schemas.py` é a fonte da verdade. O agente de roteirização:
- Valida resposta do LLM contra o schema Pydantic
- Aplica regras de negócio (duração de cenas, animações, texto destaque)
- Realiza retry com correção em caso de falha de validação
