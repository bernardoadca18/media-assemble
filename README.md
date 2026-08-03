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
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
cp .env.example .env        # preencher credenciais e paths reais
```

Banco de dados: o schema `dados` e a tabela `videos_ideias` devem existir
previamente no Postgres (mesma estrutura já usada no fluxo n8n original).
Rodar as migrations em `db/migrations/` (Alembic — a configurar) antes da
primeira execução.

## Rodando a Fase 1 isoladamente

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
| 2 | Roteirização completa | Stub (`NotImplementedError`) |
| 3 | Áudio (F5-TTS + Whisper + WER) | Stub (`NotImplementedError`) |
| 4 | Assets visuais | Stub (`NotImplementedError`) |
| 5 | Renderização (Remotion) | Stub (`NotImplementedError`) |
| 6 | Orquestração end-to-end + observabilidade | Não iniciado |
| 7 | Hardening, multi-nicho, deploy | Não iniciado |
