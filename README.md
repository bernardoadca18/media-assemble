# Media Assemble — Autonomous Multimedia System (100% Python)

> **Note (resolved):** this file had disappeared from the repository at
> some point between Phase 3 and Phase 4. An investigation using `git log --all
> --full-history -- README.md` confirmed that there was no explicit removal
> commit — the file simply stopped being tracked at some point after commit
> `c218719`. It has been fully restored; there is no indication that this will
> happen again.
>
> **Language:** English · [Versão em Português (Brasil)](README.pt-br.md)

A modular system for autonomous multimedia generation, with a 100% Python architecture
optimized for local execution on a single GPU and cloud models.

## Quick setup

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scriptsctivate on Windows
pip install -r requirements.txt
cp .env.example .env        # fill in actual credentials and paths
```

Fill in at least the following in `.env`:
- `DATABASE_URL` — Postgres connection string.
- LLM credentials (`OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY`) according to the models configured in `CLOUD_MODEL_IDEACAO` and `CLOUD_MODEL_ROTEIRO`.
- `F5_TTS_REF_AUDIO` / `F5_TTS_REF_TEXT` — voice sample for TTS (Phase 3).
- `PEXELS_API_KEY` — required for visual asset fallback (Phase 4) when the local database does not contain the asset.

### Database

Run the migrations before the first execution:

```bash
alembic upgrade head
```

This creates the `dados` schema and the `videos_ideias` table (compatible with the
original n8n flow), as well as `roteiros` and `execucoes_pipeline` (the latter
only becomes actively used in Phase 6).

## Running the pipeline

Complete pipeline (Phases 1 through 5):

```bash
python main.py --run-once
```

Or scheduled (production):

```bash
python main.py
```

## Folder structure

```
pipeline/       # Orchestration, configuration, and schemas (source of truth)
services/       # One module per pipeline stage
  trends/       # Phase 1 — trend collection and normalization
  ideation/     # Phase 1 — generation of 5 video ideas
  scripting/    # Phase 2 — full scripting in JSON
  audio/        # Phase 3 — TTS (F5-TTS) + validation (Faster-Whisper/WER)
  visual/       # Phase 4 — asset resolution (local database + Pexels fallback)
  render/       # Phase 5 — rendering via Remotion
api/            # FastAPI HTTP API for pipeline management (frontend)
db/             # SQLAlchemy models, session, and Alembic migrations
utils/          # Structured logging and unified LiteLLM client
remotion/       # Isolated Node.js/React project (Phase 5)
frontend/       # Web management interface (React + TypeScript + Vite)
data/           # Local assets, temporary audio, final output
tests/          # Automated tests
```

## Local visual asset database (Phase 4)

`data/assets_local/` is organized by **tags** — each subfolder is a tag,
and the files inside it are the assets for that tag:

```
data/assets_local/
    doctor_doom/
        img1.jpg
        img2.png
    naruto/
        clip1.mp4
```

- The folder name automatically becomes the tag (normalized to lowercase, without
  accents; spaces/hyphens are converted to `_`).
- Scene-to-tag matching is based on `midia.keywords_busca` from the script, with both
  exact and partial matching (e.g. keyword `"doctor_doom_art"` matches the `doctor_doom` tag).
- If a tag contains multiple files, one is selected randomly on each resolution —
  this prevents the same single asset from being reused throughout every video that
  references that tag.
- Folders beginning with `_` or `.` are ignored during indexing (e.g.
  `_fallback_cache/`, used internally by the Pexels fallback — do not edit manually).
- When no asset is found locally, the Pexels API fallback is triggered automatically
  (requires `PEXELS_API_KEY` in `.env`). If the fallback also finds nothing, the scene
  is marked with `revisao_manual_necessaria = True` for human review — the pipeline
  continues and never gets stuck because of a single scene without an asset.

## Concurrency principle (important)

Any call that touches the local GPU (local LLM via LiteLLM, F5-TTS,
Faster-Whisper) **must** go through `gpu_task` in `pipeline/gpu_lock.py`.
Calls to cloud models (Claude, Gemini, OpenAI) and external APIs (Pexels)
do not need this lock and can run freely in parallel.

## Running tests

```bash
pytest -v
```

## Phase status

| Phase | Scope | Status |
|---|---|---|
| 1 | Trends + Ideation | Completed |
| 2 | Full scripting | Completed |
| 3 | Audio (F5-TTS + Whisper + WER) | Completed |
| 4 | Visual assets (local database + Pexels fallback) | Completed |
| 5 | Rendering (Remotion) | Completed ✓ (validated with a real render) |
| 6 | End-to-end orchestration + observability | Completed |
| 7 | Hardening, multi-niche, deployment | Not started |

Each `rodar_pipeline_completo` execution persists the script in the database
(`db.models.salvar_roteiro`, upsert by `video_id`) after each completed phase —
Phase 2 (script generated), Phase 3 (audio populated), Phase 4 (assets resolved),
and Phase 5 (video rendered) — so progress is not lost if the process is interrupted.

## Phase 5 — Rendering (Remotion)

Phase 5 uses [Remotion](https://www.remotion.dev/) to render the final video from the populated script. The Node.js project is isolated in `remotion/` and is invoked via subprocess by the Python bridge.

### Remotion setup

```bash
cd remotion
npm install
```

### Remotion component structure

```
remotion/src/
├── index.ts              # Entry point
├── Root.tsx              # Defines the main composition
└── components/
    ├── KenBurnsImage.tsx       # Zoom/pan effect on images
    ├── SubtitlesOverlay.tsx    # Word-by-word subtitles
    ├── AudioTrack.tsx          # Narration + ducked music track
    ├── SceneRenderer.tsx       # Renders an individual scene
    └── VideoComposition.tsx    # Composes all scenes
```

### Manual rendering

To render a video manually (without the Python pipeline):

```bash
cd remotion
npx remotion render src/index.ts VideoPrincipal out/video.mp4
```

The Python bridge (`services/render/remotion_bridge.py`) automates this process by serializing the script to JSON and passing it as props to the composition.

## Phase 6 — End-to-End Orchestration and Observability

Phase 6 implements per-stage error handling, execution-state persistence, and full pipeline traceability.

### Per-stage error handling

Each of the 5 pipeline phases is wrapped in a `try/except` block:
- **Ideation (Phase 1)**: failure is recorded with `video_id=None` (not generated yet)
- **Scripting (Phase 2)**: failure is captured before `video_id` generation
- **Audio (Phase 3)**: failure is recorded with the already available `video_id`
- **Assets (Phase 4)**: failure is recorded with `video_id`
- **Rendering (Phase 5)**: failure is recorded with `video_id`

**Design decision**: when a phase fails, execution stops immediately — the pipeline **does not continue** to the next phase. This avoids unnecessary processing and ensures that each video is generated completely and consistently from start to finish.

### Execution persistence

The `dados.execucoes_pipeline` table stores the history of each execution:

| Column | Description |
|--------|-----------|
| `video_id` | Unique video identifier (or an empty string if it failed before generation) |
| `nicho` | Processed niche (e.g. `cultura_pop`) |
| `etapa_atual` | Last executed phase (`ideacao`, `roteirizacao`, `audio`, `assets`, `renderizacao`) |
| `sucesso` | `True` if completed successfully, `False` if it failed, `NULL` if still in progress |
| `caminho_video_final` | Path to the rendered video (only if `sucesso=True`) |
| `wer_medio` | Average WER across scenes (only if `sucesso=True`) |
| `criado_em` | Record creation timestamp |
| `atualizado_em` | Last update timestamp |

### Querying execution history

To view the last 10 executions:

```sql
SELECT
    video_id,
    nicho,
    etapa_atual,
    sucesso,
    wer_medio,
    caminho_video_final,
    atualizado_em
FROM dados.execucoes_pipeline
ORDER BY atualizado_em DESC
LIMIT 10;
```

To view failed executions:

```sql
SELECT video_id, etapa_atual, atualizado_em
FROM dados.execucoes_pipeline
WHERE sucesso = FALSE
ORDER BY atualizado_em DESC;
```

To view the success rate by niche:

```sql
SELECT
    nicho,
    COUNT(*) AS total,
    SUM(CASE WHEN sucesso THEN 1 ELSE 0 END) AS sucessos,
    ROUND(100.0 * SUM(CASE WHEN sucesso THEN 1 ELSE 0 END) / COUNT(*), 2) AS taxa_sucesso_pct
FROM dados.execucoes_pipeline
WHERE sucesso IS NOT NULL
GROUP BY nicho
ORDER BY nicho;
```

### Structured logging

All logs include structured fields for correlation:

```python
logger.error(
    "pipeline.roteirizacao.falhou",
    extra={
        "nicho": nicho,
        "video_id": video_id,
        "erro_tipo": type(erro).__name__,
        "erro_msg": str(erro),
    },
    exc_info=True,
)
```

This allows logs to be filtered by `video_id`, `nicho`, or error type in observability systems (Grafana Loki, ELK, etc.).

## Frontend — Management Interface

The project includes a web interface for managing the pipeline, available in `frontend/`.

### Starting the frontend

```bash
# Terminal 1: Backend API
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2: Frontend
cd frontend && npm run dev
```

Open `http://localhost:5173`.

### Features

| Page | Route | Description |
|--------|------|-----------|
| Dashboard | `/` | GPU status, statistics, recent executions |
| Executions | `/execucoes` | Full history, filters, resume failed executions |
| Manual Review | `/revisao` | Approve/reject pending scripts |
| Manual Ideas | `/ideias-manuais` | Create and list video ideas |
| Gameplay | `/gameplay` | Indexed segments, statistics by game |
| Niches | `/nichos` | Niche and channel settings |

### Security

- API bound only to `127.0.0.1` (local use)
- CORS restricted to `localhost:5173` and `localhost:3000`
- No authentication (do not expose publicly)

For full details, see `frontend/README.md`.
