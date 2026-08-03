# Guia de Arquitetura e Implementação — Sistema Autônomo de Vídeos Faceless (100% Python)

> Substituição do workflow n8n "Scrapper" por um pipeline modular Python, ponta-a-ponta, otimizado para GPU única (RTX 2060 12GB).

---

## Sumário

1. Visão geral da arquitetura e fila de execução
2. Setup do Remotion e integração com Python
3. Pipeline de áudio (F5-TTS + Faster-Whisper + WER)
4. Estratégia de originalidade / Fair Use e algoritmo do YouTube
5. System Prompt de roteirização
6. Modelagem final do JSON de roteiro

---

## 1. Visão Geral da Arquitetura e Fila de Execução

### 1.1 Decisão de orquestração: por que **não** Celery aqui

Celery brilha em cenários multi-worker/multi-máquina com broker distribuído. No seu caso — **uma única máquina, uma única GPU de 12GB, um único operador** — Celery adiciona complexidade operacional (broker Redis/RabbitMQ, workers, monitoramento) sem resolver o problema real, que é **concorrência de GPU, não concorrência de máquinas**.

A recomendação é um híbrido:

- **`asyncio`** para tudo que é I/O-bound e pode rodar em paralelo sem custo de VRAM: scraping de tendências, chamadas a APIs de LLM em nuvem (via LiteLLM), buscas de assets (Pexels/DuckDuckGo), operações de banco.
- **Um único "GPU worker" sequencial**, protegido por `asyncio.Semaphore(1)` (ou uma fila `asyncio.Queue` consumida por um único loop), para tudo que toca a RTX 2060: inferência de LLM local (Qwen/Phi-4 via LiteLLM apontando para Ollama/vLLM local), F5-TTS e Faster-Whisper. Isso garante que nunca dois processos tentem alocar VRAM simultaneamente.
- **`APScheduler`** apenas para disparar o pipeline periodicamente (substituto direto do trigger do n8n).

Se um dia você escalar para múltiplas GPUs ou múltiplas máquinas, migrar essa camada para **RQ (Redis Queue)** é um passo intermediário muito mais simples que Celery — vale mais a pena que pular direto para Celery.

### 1.2 Estrutura de diretórios recomendada

```
faceless-pipeline/
├── pipeline/
│   ├── __init__.py
│   ├── orchestrator.py        # Loop principal, agenda e dispara as etapas
│   ├── gpu_lock.py            # Semaphore/lock global para tarefas de GPU
│   ├── config.py              # Settings (pydantic-settings), paths, .env
│   └── schemas.py             # Modelos Pydantic do JSON de roteiro (fonte da verdade)
│
├── services/
│   ├── trends/
│   │   ├── scraper.py         # X/Twitter, Google Trends, Reddit, YouTube
│   │   └── normalizer.py      # Limpeza via LLM pequeno (Phi-4-mini/Qwen)
│   │
│   ├── ideation/
│   │   ├── agent.py           # Agente de ideias por nicho
│   │   └── rag_client.py      # Cliente pgvector/ChromaDB para checar duplicidade
│   │
│   ├── scripting/
│   │   └── writer_agent.py    # Gera o roteiro completo em JSON estrito
│   │
│   ├── audio/
│   │   ├── tts_engine.py      # Wrapper do F5-TTS
│   │   ├── validator.py       # Faster-Whisper + cálculo de WER
│   │   └── mixer.py           # Concatenação/mixagem via FFmpeg
│   │
│   ├── visual/
│   │   ├── asset_resolver.py  # Busca no banco local por tags
│   │   └── fallback_scraper.py# Pexels / DuckDuckGo / yt-dlp
│   │
│   └── render/
│       └── remotion_bridge.py # subprocess -> Remotion CLI
│
├── remotion/                  # Projeto Node.js/React independente
│   ├── src/
│   │   ├── compositions/
│   │   │   └── VideoComposition.tsx
│   │   ├── components/
│   │   │   ├── SceneRenderer.tsx
│   │   │   ├── KenBurnsImage.tsx
│   │   │   ├── SubtitlesOverlay.tsx
│   │   │   └── AudioTrack.tsx
│   │   └── Root.tsx
│   ├── package.json
│   └── remotion.config.ts
│
├── db/
│   ├── models.py               # SQLAlchemy models (videos_ideias, roteiros, execucoes)
│   └── migrations/             # Alembic
│
├── utils/
│   ├── logger.py               # structlog / logging estruturado em JSON
│   └── litellm_client.py       # Cliente único LiteLLM (local + cloud)
│
├── data/
│   ├── assets_local/            # Banco local de imagens/vídeos organizados por tags
│   ├── audio_temp/
│   └── output_final/
│
├── main.py                     # Entry point (dispara o orchestrator)
├── .env
└── requirements.txt
```

### 1.3 O "GPU Lock" — peça central para não estourar VRAM

```python
# pipeline/gpu_lock.py
import asyncio
import logging
from contextlib import asynccontextmanager

logger = logging.getLogger("gpu_lock")

# Único semáforo global: garante que apenas UMA tarefa
# que toca a GPU (LLM local, F5-TTS, Faster-Whisper) rode por vez.
_gpu_semaphore = asyncio.Semaphore(1)


@asynccontextmanager
async def gpu_task(task_name: str):
    """
    Uso:
        async with gpu_task("f5-tts-cena-03"):
            gerar_audio(...)
    """
    logger.info(f"[GPU] Aguardando liberação para: {task_name}")
    async with _gpu_semaphore:
        logger.info(f"[GPU] Iniciando: {task_name}")
        try:
            yield
        finally:
            logger.info(f"[GPU] Finalizado: {task_name}")
```

Todas as chamadas que envolvem VRAM (LLM local via LiteLLM, F5-TTS, Faster-Whisper) devem ser envolvidas por esse `async with gpu_task(...)`. Chamadas a modelos em nuvem (Claude, Gemini Flash, OpenAI) **não** passam por esse lock — podem rodar em paralelo livremente, pois não consomem sua VRAM local.

### 1.4 Orquestrador principal (substitui o Webhook + fluxo do n8n)

```python
# pipeline/orchestrator.py
import asyncio
import logging
from services.trends.scraper import coletar_tendencias
from services.trends.normalizer import normalizar_tendencias
from services.ideation.agent import gerar_ideias
from services.scripting.writer_agent import gerar_roteiro
from services.audio.tts_engine import gerar_audio_do_roteiro
from services.visual.asset_resolver import resolver_assets_do_roteiro
from services.render.remotion_bridge import renderizar_video
from db.models import salvar_ideias, salvar_execucao

logger = logging.getLogger("orchestrator")


async def rodar_pipeline_completo(nicho: str):
    # Etapa 1 — Scraping & Normalização (I/O-bound, pode ser paralelo)
    tendencias_brutas = await coletar_tendencias(nicho)
    tendencias = await normalizar_tendencias(tendencias_brutas)

    # Etapa 2 — Ideação com RAG (checa duplicidade antes de gastar tokens)
    ideias = await gerar_ideias(nicho=nicho, tendencias=tendencias)
    await salvar_ideias(ideias)

    # A partir daqui, escolhemos 1 ideia por execução (equivalente ao
    # "1 vídeo por rodada" do fluxo antigo em n8n)
    ideia_escolhida = ideias[0]
    roteiro = await gerar_roteiro(ideia_escolhida)

    # Etapa 3 — Áudio (GPU-bound, sequencial via gpu_lock internamente)
    roteiro_com_audio = await gerar_audio_do_roteiro(roteiro)

    # Etapa 4 — Assets visuais (I/O-bound, paralelizável)
    roteiro_com_assets = await resolver_assets_do_roteiro(roteiro_com_audio)

    # Etapa 5 — Render (subprocess bloqueante, roda isolado)
    caminho_final = await renderizar_video(roteiro_com_assets)

    await salvar_execucao(roteiro_com_assets, caminho_final)
    logger.info(f"Vídeo finalizado: {caminho_final}")
    return caminho_final


if __name__ == "__main__":
    asyncio.run(rodar_pipeline_completo(nicho="cultura_pop"))
```

O agendamento periódico (substituindo o trigger do n8n) fica em `main.py` com `APScheduler`:

```python
# main.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import asyncio
from pipeline.orchestrator import rodar_pipeline_completo

scheduler = AsyncIOScheduler()

# Roda o pipeline 1x por dia às 06:00 para o nicho de cultura pop
scheduler.add_job(rodar_pipeline_completo, "cron", hour=6, args=["cultura_pop"])

if __name__ == "__main__":
    scheduler.start()
    try:
        asyncio.get_event_loop().run_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
```

### 1.5 Migração direta do seu fluxo n8n atual

Mapeando o que existia no `Scrapper.json` para os novos módulos Python:

| Nó n8n | Módulo Python equivalente |
|---|---|
| `Webhook` | `main.py` (trigger via APScheduler) ou endpoint FastAPI opcional |
| `Execute a SQL query` (histórico) | `db/models.py::buscar_historico_titulos()` |
| `Message a model1` (prompt + Gemini Flash) | `services/ideation/agent.py` (via LiteLLM) |
| `Code in JavaScript` (parser do JSON) | `pipeline/schemas.py` (validação via Pydantic, muito mais robusta que regex) |
| `Insert rows in a table` | `db/models.py::salvar_ideias()` |

Vantagem imediata de migrar o parser do JavaScript para **Pydantic**: em vez de `try/except JSON.parse` manual, você ganha validação de schema, mensagens de erro estruturadas e retry automático em caso de resposta malformada do LLM.

```python
# pipeline/schemas.py
from pydantic import BaseModel, Field

class Ideia(BaseModel):
    topico: str
    titulo_sugerido: str
    descricao_breve: str

class RespostaIdeacao(BaseModel):
    ideias: list[Ideia] = Field(min_length=5, max_length=5)
```

```python
# services/ideation/agent.py (trecho de parsing robusto)
import json
from pipeline.schemas import RespostaIdeacao

def parsear_resposta_llm(texto_bruto: str) -> RespostaIdeacao:
    texto_limpo = texto_bruto.replace("```json", "").replace("```", "").strip()
    dados = json.loads(texto_limpo)          # levanta JSONDecodeError se inválido
    return RespostaIdeacao.model_validate(dados)  # levanta ValidationError se schema errado
```

---

## 2. Setup do Remotion e Integração com Python

### 2.1 Por que manter o Remotion em Node.js (e não tentar substituí-lo)

Remotion é React renderizado quadro a quadro para vídeo — não existe equivalente maduro em Python com o mesmo nível de controle de animação, timeline e composição declarativa. A integração correta **não é** reescrever isso em Python, e sim tratar o projeto Remotion como um **serviço de renderização isolado**, chamado via `subprocess` a partir do seu orquestrador Python — exatamente como você já planejou.

### 2.2 Estrutura do projeto Remotion

```
remotion/
├── src/
│   ├── Root.tsx                  # Registra a composição principal
│   ├── compositions/
│   │   └── VideoComposition.tsx  # Composição raiz, recebe o roteiro como props
│   └── components/
│       ├── SceneRenderer.tsx     # Renderiza uma cena (imagem/vídeo + overlays)
│       ├── KenBurnsImage.tsx     # Efeito de zoom/pan suave
│       ├── SubtitlesOverlay.tsx  # Legendas dinâmicas palavra-a-palavra
│       └── AudioTrack.tsx        # Trilha + narração + ducking
├── package.json
└── remotion.config.ts
```

### 2.3 `Root.tsx` — registrando a composição com duração dinâmica

```tsx
// src/Root.tsx
import { Composition } from "remotion";
import { VideoComposition } from "./compositions/VideoComposition";
import roteiroExemplo from "../../data/roteiro_exemplo.json";

const FPS = 30;

export const RemotionRoot: React.FC = () => {
  const duracaoEmFrames = Math.round(
    roteiroExemplo.metadata.duracao_estimada_segundos * FPS
  );

  return (
    <Composition
      id="VideoPrincipal"
      component={VideoComposition}
      durationInFrames={duracaoEmFrames}
      fps={FPS}
      width={1080}
      height={1920} // formato vertical (Shorts) — ajuste para 1920x1080 se for widescreen
      defaultProps={{ roteiro: roteiroExemplo }}
    />
  );
};
```

### 2.4 `KenBurnsImage.tsx` — efeito de zoom suave

```tsx
// src/components/KenBurnsImage.tsx
import { AbsoluteFill, Img, interpolate, useCurrentFrame } from "remotion";

interface Props {
  src: string;
  durationInFrames: number;
  direction?: "zoom_in" | "zoom_out";
}

export const KenBurnsImage: React.FC<Props> = ({
  src,
  durationInFrames,
  direction = "zoom_in",
}) => {
  const frame = useCurrentFrame();

  const scale = interpolate(
    frame,
    [0, durationInFrames],
    direction === "zoom_in" ? [1.0, 1.15] : [1.15, 1.0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // Leve deslocamento horizontal para reforçar a sensação de movimento
  const translateX = interpolate(frame, [0, durationInFrames], [0, -20], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={src}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translateX(${translateX}px)`,
        }}
      />
    </AbsoluteFill>
  );
};
```

### 2.5 `SubtitlesOverlay.tsx` — legendas dinâmicas estilo CapCut/TikTok

Usa os timestamps por palavra que o **Faster-Whisper** já gera na etapa de validação de áudio (veja seção 3), reaproveitando esse dado em vez de gerar legendas separadamente.

```tsx
// src/components/SubtitlesOverlay.tsx
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";

interface Word {
  text: string;
  start: number; // segundos, absoluto no vídeo
  end: number;
}

interface Props {
  words: Word[];
}

export const SubtitlesOverlay: React.FC<Props> = ({ words }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const tempoAtual = frame / fps;

  // Agrupa em pequenas janelas de 3-4 palavras (mais legível que frase inteira)
  const palavraAtivaIndex = words.findIndex(
    (w) => tempoAtual >= w.start && tempoAtual <= w.end
  );
  if (palavraAtivaIndex === -1) return null;

  const inicioJanela = Math.max(0, palavraAtivaIndex - 1);
  const janela = words.slice(inicioJanela, inicioJanela + 4);

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: 220,
      }}
    >
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap", maxWidth: "85%" }}>
        {janela.map((w, i) => {
          const ativa = words[inicioJanela + i] === words[palavraAtivaIndex];
          return (
            <span
              key={i}
              style={{
                fontFamily: "Montserrat, sans-serif",
                fontWeight: 800,
                fontSize: 64,
                color: ativa ? "#FFD700" : "#FFFFFF",
                WebkitTextStroke: "3px black",
                textTransform: "uppercase",
                transform: ativa ? "scale(1.1)" : "scale(1.0)",
                transition: "transform 0.1s",
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
```

### 2.6 `AudioTrack.tsx` — narração + trilha com ducking automático

```tsx
// src/components/AudioTrack.tsx
import { Audio, Sequence, interpolate, useCurrentFrame } from "remotion";

interface Props {
  narracaoSrc: string;
  trilhaSrc: string;
  volumeTrilha: number; // ex: 0.15
  totalDurationInFrames: number;
}

export const AudioTrack: React.FC<Props> = ({
  narracaoSrc,
  trilhaSrc,
  volumeTrilha,
  totalDurationInFrames,
}) => {
  const frame = useCurrentFrame();

  // Ducking simples: reduz a trilha nos primeiros/últimos frames de cada
  // fade e mantém volume constante e baixo durante a narração.
  // Para ducking reativo ao volume real da voz, pré-processar via análise
  // de amplitude no Python e passar um array de multiplicadores como prop.
  const fadeIn = interpolate(frame, [0, 30], [0, volumeTrilha], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [totalDurationInFrames - 30, totalDurationInFrames],
    [volumeTrilha, 0],
    { extrapolateLeft: "clamp" }
  );
  const volumeFinal = Math.min(fadeIn, fadeOut, volumeTrilha);

  return (
    <>
      <Audio src={narracaoSrc} volume={1.0} />
      <Sequence from={0} durationInFrames={totalDurationInFrames}>
        <Audio src={trilhaSrc} volume={volumeFinal} loop />
      </Sequence>
    </>
  );
};
```

### 2.7 `VideoComposition.tsx` — orquestrando as cenas

```tsx
// src/compositions/VideoComposition.tsx
import { Series } from "remotion";
import { SceneRenderer } from "../components/SceneRenderer";
import { SubtitlesOverlay } from "../components/SubtitlesOverlay";
import { AudioTrack } from "../components/AudioTrack";

const FPS = 30;

export const VideoComposition: React.FC<{ roteiro: any }> = ({ roteiro }) => {
  const totalFrames = Math.round(roteiro.metadata.duracao_estimada_segundos * FPS);

  return (
    <>
      <Series>
        {roteiro.cenas.map((cena: any) => (
          <Series.Sequence
            key={cena.cena_id}
            durationInFrames={Math.round(cena.duracao_estimada_segundos * FPS)}
          >
            <SceneRenderer cena={cena} />
          </Series.Sequence>
        ))}
      </Series>

      <SubtitlesOverlay words={roteiro.metadata.palavras_transcritas} />

      <AudioTrack
        narracaoSrc={roteiro.metadata.audio_final_path}
        trilhaSrc={`../../data/musicas/${roteiro.metadata.trilha_fundo}`}
        volumeTrilha={roteiro.metadata.volume_trilha_fundo}
        totalDurationInFrames={totalFrames}
      />
    </>
  );
};
```

### 2.8 Disparando a renderização a partir do Python

```python
# services/render/remotion_bridge.py
import json
import subprocess
import tempfile
from pathlib import Path

REMOTION_DIR = Path(__file__).resolve().parents[2] / "remotion"


async def renderizar_video(roteiro: dict) -> Path:
    """
    Serializa o roteiro em um arquivo temporário e dispara a CLI do Remotion.
    A chamada é bloqueante (subprocess.run), então deve rodar em thread
    separada para não travar o loop asyncio.
    """
    import asyncio

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(roteiro, f, ensure_ascii=False)
        props_path = f.name

    saida = Path("data/output_final") / f"{roteiro['metadata']['video_id']}.mp4"
    saida.parent.mkdir(parents=True, exist_ok=True)

    comando = [
        "npx",
        "remotion",
        "render",
        "VideoPrincipal",
        str(saida),
        f"--props={props_path}",
        "--concurrency=1",  # importante: evita competir por recursos com a GPU
    ]

    def _executar():
        resultado = subprocess.run(
            comando, cwd=REMOTION_DIR, capture_output=True, text=True
        )
        if resultado.returncode != 0:
            raise RuntimeError(f"Falha na renderização Remotion:\n{resultado.stderr}")
        return saida

    return await asyncio.to_thread(_executar)
```

`--concurrency=1` no Remotion é intencional: como a mesma máquina hospeda a RTX 2060 usada pelo TTS/Whisper, evitar que o Remotion (que usa Chrome headless para renderizar) dispute recursos de GPU/CPU agressivamente durante a fase de render.

---

## 3. Pipeline de Áudio em Python (F5-TTS + Faster-Whisper + WER)

### 3.1 Fluxo completo

1. Iterar cada `cena` do roteiro.
2. Gerar áudio via F5-TTS (zero-shot com sua amostra de voz).
3. Transcrever esse áudio com Faster-Whisper.
4. Calcular WER entre `texto_locucao` original e a transcrição.
5. Se WER > 5% (ou seja, precisão < 95%), regenerar com nova seed (até N tentativas).
6. Salvar os timestamps por palavra (usados depois nas legendas do Remotion).
7. Concatenar todos os áudios aprovados em um único arquivo master via FFmpeg.

### 3.2 Wrapper do F5-TTS

```python
# services/audio/tts_engine.py
import random
from pathlib import Path
from f5_tts.api import F5TTS  # ajuste conforme a API real da lib instalada

from pipeline.gpu_lock import gpu_task

_modelo_tts = None


def _carregar_modelo():
    global _modelo_tts
    if _modelo_tts is None:
        _modelo_tts = F5TTS(
            model_type="F5-TTS",
            ref_audio="data/voz_referencia/minha_voz.wav",
            ref_text="Transcrição exata do áudio de referência.",
        )
    return _modelo_tts


async def gerar_audio_cena(texto: str, saida: Path, seed: int | None = None) -> Path:
    seed = seed or random.randint(0, 999_999)
    async with gpu_task(f"f5-tts-{saida.stem}"):
        modelo = _carregar_modelo()
        modelo.infer(
            gen_text=texto,
            file_wave=str(saida),
            seed=seed,
            speed=1.0,
        )
    return saida
```

### 3.3 Validação via Faster-Whisper + WER (Levenshtein)

```python
# services/audio/validator.py
from dataclasses import dataclass
from pathlib import Path
from faster_whisper import WhisperModel

from pipeline.gpu_lock import gpu_task

_modelo_whisper = WhisperModel("medium", device="cuda", compute_type="float16")


@dataclass
class ResultadoValidacao:
    aprovado: bool
    wer: float
    texto_transcrito: str
    palavras: list[dict]  # [{"text": ..., "start": ..., "end": ...}, ...]


def _distancia_levenshtein(a: list[str], b: list[str]) -> int:
    """Distância de edição clássica em nível de palavra (base do cálculo de WER)."""
    n, m = len(a), len(b)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        dp[i][0] = i
    for j in range(m + 1):
        dp[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            custo = 0 if a[i - 1] == b[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deleção
                dp[i][j - 1] + 1,      # inserção
                dp[i - 1][j - 1] + custo,  # substituição
            )
    return dp[n][m]


def calcular_wer(texto_referencia: str, texto_transcrito: str) -> float:
    ref_palavras = texto_referencia.lower().split()
    hip_palavras = texto_transcrito.lower().split()
    if not ref_palavras:
        return 0.0
    distancia = _distancia_levenshtein(ref_palavras, hip_palavras)
    return distancia / len(ref_palavras)


async def validar_audio(
    caminho_audio: Path, texto_esperado: str, limite_wer: float = 0.05
) -> ResultadoValidacao:
    async with gpu_task(f"whisper-validate-{caminho_audio.stem}"):
        segments, _info = _modelo_whisper.transcribe(
            str(caminho_audio), word_timestamps=True, language="pt"
        )
        segments = list(segments)

    texto_transcrito = " ".join(s.text.strip() for s in segments)
    palavras = [
        {"text": w.word.strip(), "start": w.start, "end": w.end}
        for s in segments
        for w in s.words
    ]

    wer = calcular_wer(texto_esperado, texto_transcrito)
    return ResultadoValidacao(
        aprovado=wer <= limite_wer,
        wer=wer,
        texto_transcrito=texto_transcrito,
        palavras=palavras,
    )
```

### 3.4 Loop de geração com retry por seed

```python
# services/audio/pipeline_audio.py
from pathlib import Path
from services.audio.tts_engine import gerar_audio_cena
from services.audio.validator import validar_audio

MAX_TENTATIVAS = 3


async def gerar_e_validar_cena(cena: dict, dir_temp: Path) -> dict:
    saida = dir_temp / f"cena_{cena['cena_id']:03d}.wav"
    texto = cena["texto_locucao"]

    for tentativa in range(1, MAX_TENTATIVAS + 1):
        await gerar_audio_cena(texto, saida, seed=None)  # seed aleatória a cada tentativa
        resultado = await validar_audio(saida, texto)

        if resultado.aprovado:
            cena["audio_path"] = str(saida)
            cena["palavras_transcritas"] = resultado.palavras
            cena["wer_final"] = resultado.wer
            return cena

        print(
            f"[Cena {cena['cena_id']}] Tentativa {tentativa} reprovada "
            f"(WER={resultado.wer:.2%}). Regenerando..."
        )

    # Após esgotar tentativas, aceita a última mesmo assim mas sinaliza para revisão manual
    cena["audio_path"] = str(saida)
    cena["revisao_manual_necessaria"] = True
    return cena


async def gerar_audio_do_roteiro(roteiro: dict) -> dict:
    dir_temp = Path("data/audio_temp") / roteiro["metadata"]["video_id"]
    dir_temp.mkdir(parents=True, exist_ok=True)

    cenas_processadas = []
    for cena in roteiro["cenas"]:
        cena_pronta = await gerar_e_validar_cena(cena, dir_temp)
        cenas_processadas.append(cena_pronta)

    roteiro["cenas"] = cenas_processadas
    roteiro["metadata"]["audio_final_path"] = await concatenar_audios(
        cenas_processadas, dir_temp
    )
    return roteiro
```

### 3.5 Concatenação final via FFmpeg

```python
# services/audio/mixer.py
import asyncio
from pathlib import Path


async def concatenar_audios(cenas: list[dict], dir_temp: Path) -> str:
    lista_path = dir_temp / "lista_concat.txt"
    with open(lista_path, "w", encoding="utf-8") as f:
        for cena in cenas:
            # FFmpeg concat demuxer exige paths absolutos ou escapados corretamente
            caminho_abs = Path(cena["audio_path"]).resolve()
            f.write(f"file '{caminho_abs}'\n")

    saida = dir_temp / "narracao_final.wav"
    comando = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(lista_path),
        "-c", "copy",
        str(saida),
    ]

    processo = await asyncio.create_subprocess_exec(
        *comando, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _stdout, stderr = await processo.communicate()
    if processo.returncode != 0:
        raise RuntimeError(f"Erro no FFmpeg: {stderr.decode()}")

    return str(saida)
```

> **Nota sobre a métrica de 95%:** WER de 5% é um limiar razoável para narração (permite pequenas variações de pontuação/artigos que o TTS às vezes introduz), mas para nomes próprios ou termos técnicos de nicho (nomes de personagens, jogos) considere normalizar ambos os textos (remover acentuação, minúsculas, remover pontuação) antes de comparar — senão você vai gerar falsos negativos e queimar tentativas à toa.

---

## 4. Estratégia de Originalidade / Fair Use e Algoritmo do YouTube

Importante deixar claro o enquadramento: não existe uma "receita" para burlar sistemas de detecção de conteúdo (Content ID) — e mesmo que existisse, tentar contornar deliberadamente a detecção de copyright é a receita mais rápida para strike e possível encerramento de canal. O caminho sólido e sustentável é **produzir conteúdo genuinamente transformativo e com assets licenciados corretamente**, o que resolve o problema pela raiz em vez de tentar escapar de um radar.

### 4.1 Práticas de edição que geram valor transformativo real

- **Narração original e analítica é o seu maior ativo de Fair Use.** O canal já está estruturado assim (explicações, listas, análise de lore) — isso é exatamente o tipo de comentário/crítica/educação que caracteriza uso transformativo, diferente de reupload puro.
- **Nunca use trechos longos e contínuos de uma única fonte visual.** Prefira cortes de poucos segundos, intercalando múltiplas fontes (arte, fan art licenciada, imagens 3D geradas, clipes curtos) em vez de um vídeo/imagem única carregando a cena inteira.
- **Transforme visualmente o asset**: Ken Burns (zoom/pan) já ajuda, mas também vale aplicar leve grading de cor consistente com a identidade do canal, crops, ou composição em camadas (imagem + partículas + overlay de texto) — isso também melhora a experiência do espectador, não é só sobre "disfarçar" a fonte.
- **Prefira bancos de assets com licença comercial clara** (Pexels, Pixabay, Unsplash para imagens/vídeos livres; Epidemic Sound, Artlist ou Envato Elements para música, que cobrem uso comercial no YouTube). Evite scraping de imagens da Google Images para uso final — sirva apenas como fallback de *referência visual* para gerar arte própria (ex: via geração de imagem), não como asset final direto de fontes sem licença.
- **`yt-dlp` para reaproveitar trechos de vídeos de terceiros é a prática de maior risco jurídico e de Content ID.** Se usar, restrinja a clipes muito curtos, claramente subordinados à sua narração/análise (function: ilustrar um ponto específico, não substituir a obra), e trate como último recurso, não como fonte primária.

### 4.2 Evitar padrão "robótico" e maximizar retenção

- **Varie ritmo de corte por cena** (não deixe todas as cenas com exatamente a mesma duração — no seu JSON, isso significa não usar sempre `duracao_estimada_segundos` fixo; deixe o roteirista variar entre ~3s e ~8s por cena conforme a densidade da informação).
- **Varie o tipo de animação** entre `ken_burns_zoom_in`, `zoom_out`, leve `pan` lateral — alternar evita padronização visual perceptível.
- **Use `overlays.texto_destaque_tela` com moderação e timing coordenado com picos de informação** (nomes próprios, números, revelações) — isso é o que mais segura retenção em conteúdo de lore/explicação.
- **Ducking de trilha real** (não apenas fade fixo): idealmente, analise a amplitude RMS da narração no Python (`librosa` ou `pydub`) e gere um array de multiplicadores de volume por frame, passado como prop para o `AudioTrack.tsx` — fica muito mais natural que um fade estático.
- **Varie o ritmo de fala/pausas entre cenas** — no F5-TTS, pequenas variações de `speed` (0.95–1.05) entre cenas evitam a sensação de "robô monotônico" sem comprometer a validação de WER.

---

## 5. System Prompt Profissional para o Agente de Roteirização

Este prompt assume que o agente já recebeu a `ideia` aprovada (tópico + título + descrição breve) na etapa anterior e agora precisa expandir isso no roteiro completo em JSON, no formato exigido pelo pipeline de áudio/vídeo.

```
Você é um Roteirista Sênior especializado em vídeos "Faceless" de Cultura Pop, Nerd e Lore
profunda para YouTube. Seu roteiro será consumido diretamente por um pipeline automatizado
de Text-to-Speech e renderização de vídeo — portanto a saída deve ser JSON estritamente
válido, sem nenhum texto fora da estrutura pedida.

CONTEXTO RECEBIDO:
- Tópico: {{topico}}
- Título sugerido: {{titulo_sugerido}}
- Ângulo/descrição breve: {{descricao_breve}}
- Duração alvo total do vídeo: {{duracao_alvo_segundos}} segundos

DIRETRIZES DE ESCRITA:
1. Divida o roteiro em cenas curtas (entre 3 e 8 segundos de narração cada). Cada cena deve
   carregar UMA única ideia ou fato — nunca acumule múltiplas informações densas numa só cena.
2. A narração deve soar como um narrador humano, especialista e envolvido no assunto — frases
   com ritmo natural de fala, evitando estruturas robóticas ou excessivamente formais.
3. Abra com um gancho forte nos primeiros 3-5 segundos (uma pergunta intrigante, uma
   afirmação polêmica ou um fato chocante relacionado ao tema) para reter o espectador logo
   de início.
4. Para cada cena, sugira de 2 a 3 `keywords_busca` específicas e visuais (em português E em
   inglês, já que bancos de imagem internacionais indexam melhor em inglês) que representem
   fielmente o que está sendo narrado naquele trecho.
5. Alterne o tipo de animação (`ken_burns_zoom_in`, `ken_burns_zoom_out`, `pan_lateral`) entre
   cenas consecutivas — nunca repita o mesmo efeito mais de duas vezes seguidas.
6. Use `texto_destaque_tela` apenas em momentos de real impacto informativo (nome de
   personagem revelado, número/estatística, virada narrativa) — não em toda cena.
7. Feche com uma cena de encerramento que resuma o gancho emocional do vídeo e sugira
   implicitamente conteúdo relacionado (sem call-to-action piegas).
8. NUNCA insira comentário, explicação ou markdown fora do JSON. A resposta deve começar
   diretamente com `{` e terminar com `}`.

FORMATO DE SAÍDA (JSON ESTRITO):
{
  "metadata": {
    "video_id": "slug_unico_em_snake_case",
    "nicho": "cultura_pop",
    "titulo_sugerido": "{{titulo_sugerido}}",
    "duracao_estimada_segundos": <soma das durações das cenas>,
    "trilha_fundo": "nome_sugerido_do_estilo_musical.mp3",
    "volume_trilha_fundo": 0.15
  },
  "cenas": [
    {
      "cena_id": 1,
      "ordem": 1,
      "texto_locucao": "Texto exato a ser narrado nesta cena.",
      "duracao_estimada_segundos": 5.2,
      "midia": {
        "tipo_asset_preferencial": "imagem",
        "keywords_busca": ["termo pt-br específico", "specific english term"],
        "fallback_query": "termo genérico de busca",
        "duracao_minima": 5.0
      },
      "efeitos_visuais": {
        "animacao_imagem": "ken_burns_zoom_in",
        "transicao_saida": "fade",
        "duracao_transicao_segundos": 0.5
      },
      "overlays": {
        "exibir_legenda": true,
        "texto_destaque_tela": "TEXTO OU NULL SE NAO APLICAVEL"
      }
    }
  ]
}

Gere agora o roteiro completo seguindo rigorosamente esta estrutura.
```

---

## 6. Modelagem Final do JSON de Roteiro — Ajustes Sugeridos

Sua estrutura original está sólida. Duas adições valem a pena, já refletidas nos exemplos de código acima:

- **`metadata.audio_final_path`** e **`metadata.palavras_transcritas`**: preenchidos automaticamente pela etapa de áudio (seção 3), consumidos diretamente pelo `AudioTrack.tsx` e `SubtitlesOverlay.tsx` no Remotion — evita ter que re-transcrever ou recalcular timestamps na camada de renderização.
- **`cena.wer_final`** e **`cena.revisao_manual_necessaria`**: metadados de controle de qualidade que não afetam o Remotion, mas alimentam um dashboard simples (ou apenas um log) para você revisar manualmente as cenas que não bateram o limiar de WER — importante para não deixar erros de pronúncia passarem despercebidos em produção 100% automatizada.

```json
{
  "metadata": {
    "video_id": "marvel_doc_doom_001",
    "nicho": "cultura_pop",
    "titulo_sugerido": "Todos os Segredos da Armadura do Doutor Destino Explicados",
    "duracao_estimada_segundos": 180,
    "trilha_fundo": "dark_ambient_synth_02.mp3",
    "volume_trilha_fundo": 0.15,
    "audio_final_path": "data/audio_temp/marvel_doc_doom_001/narracao_final.wav",
    "palavras_transcritas": [
      {"text": "O", "start": 0.0, "end": 0.12},
      {"text": "Doutor", "start": 0.12, "end": 0.48}
    ]
  },
  "cenas": [
    {
      "cena_id": 1,
      "ordem": 1,
      "texto_locucao": "O Doutor Destino é indiscutivelmente um dos vilões mais complexos e fascinantes de toda a Marvel.",
      "duracao_estimada_segundos": 5.2,
      "audio_path": "data/audio_temp/marvel_doc_doom_001/cena_001.wav",
      "wer_final": 0.02,
      "revisao_manual_necessaria": false,
      "midia": {
        "tipo_asset_preferencial": "imagem",
        "keywords_busca": ["Doctor Doom comic art dark", "Doutor Destino quadrinhos hd"],
        "fallback_query": "Doctor Doom Marvel",
        "duracao_minima": 5.0
      },
      "efeitos_visuais": {
        "animacao_imagem": "ken_burns_zoom_in",
        "transicao_saida": "fade",
        "duracao_transicao_segundos": 0.5
      },
      "overlays": {
        "exibir_legenda": true,
        "texto_destaque_tela": "VICTOR VON DOOM"
      }
    }
  ]
}
```

---

## Próximos passos sugeridos

1. Subir o esqueleto de diretórios acima e migrar primeiro a etapa de ideação (é a que já existe e valida rápido, comparando com o output atual do n8n).
2. Implementar o `gpu_lock` e validar com um teste simples de duas tarefas concorrentes tentando usar a GPU — confirmar que o semáforo realmente serializa.
3. Only depois de áudio + legendas estarem validados end-to-end, plugar o Remotion — é a etapa mais cara em tempo de desenvolvimento e você quer testá-la contra dados reais, não mocks.
