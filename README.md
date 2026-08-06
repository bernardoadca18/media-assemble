# Faceless Pipeline — Sistema Autônomo de Vídeos (100% Python)

> **Nota (resolvida):** este arquivo havia desaparecido do repositório em
> algum ponto entre a Fase 3 e a Fase 4. Investigação via `git log --all
> --full-history -- README.md` confirmou que não houve um commit de
> remoção explícito — o arquivo simplesmente deixou de ser rastreado em
> algum momento após o commit `c218719`. Restaurado integralmente; sem
> indício de que vá se repetir.

Sistema modular para geração autônoma de vídeos "faceless" para YouTube,
substituindo o fluxo n8n `Scrapper` por uma arquitetura 100% Python,
otimizada para execução local com GPU única (RTX 2060, 12GB VRAM).

## Setup rápido

```bash
python -m venv .venv
source .venv/bin/activate  # ou .venv\Scripts\activate no Windows
pip install -r requirements.txt
cp .env.example .env        # preencher credenciais e paths reais
```

Preencha no `.env`, no mínimo:
- `DATABASE_URL` — string de conexão do Postgres.
- Credenciais de LLM (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`) conforme os modelos configurados em `CLOUD_MODEL_IDEACAO` e `CLOUD_MODEL_ROTEIRO`.
- `F5_TTS_REF_AUDIO` / `F5_TTS_REF_TEXT` — amostra de voz para o TTS (Fase 3).
- `PEXELS_API_KEY` — necessária para o fallback de assets visuais (Fase 4) quando o banco local não tiver o asset.

### Banco de dados

Rode as migrations antes da primeira execução:

```bash
alembic upgrade head
```

Isso cria o schema `dados` e as tabelas `videos_ideias` (compatível com o
fluxo n8n original), `roteiros` e `execucoes_pipeline` (esta última só
passa a ser usada de fato na Fase 6).

## Rodando o pipeline

Pipeline completo (Fases 1 a 5):

```bash
python main.py --run-once
```

Ou agendado (produção):

```bash
python main.py
```

## Estrutura de pastas

```
pipeline/       # Orquestração, configuração e schemas (fonte da verdade)
services/       # Um módulo por etapa do pipeline
  trends/       # Fase 1 — coleta e normalização de tendências
  ideation/     # Fase 1 — geração de 5 ideias de vídeo
  scripting/    # Fase 2 — roteirização completa em JSON
  audio/        # Fase 3 — TTS (F5-TTS) + validação (Faster-Whisper/WER)
  visual/       # Fase 4 — resolução de assets (banco local + fallback Pexels)
  render/       # Fase 5 — renderização via Remotion
db/             # Modelos SQLAlchemy, sessão e migrations Alembic
utils/          # Logging estruturado e cliente unificado LiteLLM
remotion/       # Projeto Node.js/React isolado (Fase 5)
data/           # Assets locais, áudio temporário, saída final
tests/          # Testes automatizados
```

## Banco local de assets visuais (Fase 4)

`data/assets_local/` é organizado por **tags** — cada subpasta é uma tag,
e os arquivos dentro dela são os assets daquela tag:

```
data/assets_local/
    doctor_doom/
        img1.jpg
        img2.png
    naruto/
        clip1.mp4
```

- O nome da pasta vira a tag automaticamente (normalizado: minúsculas, sem
  acentos, espaços/hífens viram `_`).
- O casamento de uma cena com uma tag é feito a partir de
  `midia.keywords_busca` do roteiro, com correspondência exata e também
  parcial (ex: keyword `"doctor_doom_art"` casa com a tag `doctor_doom`).
- Se uma tag tiver múltiplos arquivos, um é escolhido aleatoriamente a
  cada resolução — evita que o mesmo asset único seja reaproveitado em
  todo vídeo que referencia aquela tag.
- Pastas começando com `_` ou `.` são ignoradas na indexação (ex:
  `_fallback_cache/`, usada internamente pelo fallback do Pexels — não
  edite manualmente).
- Quando nenhum asset é encontrado localmente, o fallback via Pexels API
  é acionado automaticamente (requer `PEXELS_API_KEY` no `.env`). Se nem
  o fallback encontrar nada, a cena é marcada com
  `revisao_manual_necessaria = True` para revisão humana — o pipeline
  segue adiante, nunca trava por causa de uma única cena sem asset.

## Princípio de concorrência (importante)

Toda chamada que toca a GPU local (LLM local via LiteLLM, F5-TTS,
Faster-Whisper) **deve** passar pelo `gpu_task` de `pipeline/gpu_lock.py`.
Chamadas a modelos em nuvem (Claude, Gemini, OpenAI) e a APIs externas
(Pexels) não precisam desse lock e podem rodar em paralelo livremente.

## Rodando os testes

```bash
pytest -v
```

## Status das fases

| Fase | Escopo | Status |
|---|---|---|
| 1 | Tendências + Ideação | Concluída |
| 2 | Roteirização completa | Concluída |
| 3 | Áudio (F5-TTS + Whisper + WER) | Concluída |
| 4 | Assets visuais (banco local + fallback Pexels) | Concluída |
| 5 | Renderização (Remotion) | Concluída ✓ (validado com render real) |
| 6 | Orquestração end-to-end + observabilidade | Não iniciado |
| 7 | Hardening, multi-nicho, deploy | Não iniciado |

Cada execução de `rodar_pipeline_completo` persiste o roteiro no banco
(`db.models.salvar_roteiro`, upsert por `video_id`) após cada fase
concluída — Fase 2 (roteiro gerado), Fase 3 (áudio preenchido), Fase 4
(assets resolvidos) e Fase 5 (vídeo renderizado) — para que o progresso
não se perca se o processo for interrompido.

## Fase 5 — Renderização (Remotion)

A Fase 5 utiliza o [Remotion](https://www.remotion.dev/) para renderizar o vídeo final a partir do roteiro populado. O projeto Node.js está isolado em `remotion/` e é invocado via subprocess pelo bridge Python.

### Setup do Remotion

```bash
cd remotion
npm install
```

### Estrutura dos componentes Remotion

```
remotion/src/
├── index.ts              # Entry point
├── Root.tsx              # Define composição principal
└── components/
    ├── KenBurnsImage.tsx       # Efeito zoom/pan em imagens
    ├── SubtitlesOverlay.tsx    # Legendas palavra-a-palavra
    ├── AudioTrack.tsx          # Narração + trilha com ducking
    ├── SceneRenderer.tsx       # Renderiza cena individual
    └── VideoComposition.tsx    # Compõe todas as cenas
```

### Renderização manual

Para renderizar um vídeo manualmente (sem o pipeline Python):

```bash
cd remotion
npx remotion render src/index.ts VideoPrincipal out/video.mp4
```

O bridge Python (`services/render/remotion_bridge.py`) automatiza esse processo, serializando o roteiro para JSON e passando como props para a composição.