# Auditoria do Backend — Passo 0 (Frontend de Gestão)

> Auditado em: 2026-08-09
> Objetivo: Mapear estado real dos endpoints, comandos CLI, tabelas e configurações antes de construir o frontend.

---

## 1. Endpoints Existentes (`api/status.py`)

### 1.1 Endpoints Atuais

| Endpoint | Método | Propósito | Parâmetros | Resposta |
|----------|--------|-----------|------------|----------|
| `/health` | GET | Health check | - | `{status, timestamp}` |
| `/execucoes` | GET | Lista execuções | `nicho?`, `status?`, `limite?` | `ExecucaoResumo[]` |
| `/execucoes/{video_id}` | GET | Detalhe execução | `video_id` | `ExecucaoDetalhe` |
| `/execucoes/{video_id}/metadata` | GET | Metadata publicação | `video_id` | `MetadataPublicacaoResposta` |
| `/ideias-manuais` | POST | Criar ideia manual | `IdeiaManualCreate` body | `IdeiaManualResposta` |
| `/ideias-manuais` | GET | Listar ideias manuais | `nicho?`, `status?`, `limite?` | `IdeiaManualResposta[]` |
| `/ideias-manuais/{ideia_id}` | DELETE | Descartar ideia manual | `ideia_id` | `{message, id}` |

### 1.2 Schemas Pydantic Existentes

**ExecucaoResumo:**
```typescript
{
  video_id: string
  nicho: string
  etapa_atual: string
  sucesso: boolean | null
  motivo_falha: string | null
  criado_em: string
}
```

**ExecucaoDetalhe:**
```typescript
{
  video_id: string
  nicho: string
  etapa_atual: string
  sucesso: boolean | null
  caminho_video_final: string | null
  wer_medio: number | null
  motivo_falha: string | null
  criado_em: string
}
```

**MetadataPublicacaoResposta:**
```typescript
{
  titulos: string[]
  descricao: string
  tags: string[]
  playlist_sugerida: string
  playlist_nova: boolean
}
```

**IdeiaManualCreate:**
```typescript
{
  nicho: string
  titulo_sugerido: string
  descricao_breve?: string
  tendencia_relacionada?: string
  prioridade: "alta" | "normal"
}
```

**IdeiaManualResposta:**
```typescript
{
  id: number
  nicho: string
  titulo_sugerido: string
  descricao_breve?: string
  tendencia_relacionada?: string
  prioridade: string
  status: string
  video_id?: string
  criado_em: string
}
```

### 1.3 Endpoints Faltantes (Identificados)

| Endpoint | Necessidade | Prioridade |
|----------|-------------|------------|
| `POST /execucoes/{video_id}/retomar` | Retomar execução falha | Alta |
| `GET /revisao/pendentes` | Fila de revisão manual | Alta |
| `POST /revisao/{video_id}/aprovar` | Aprovar roteiro | Alta |
| `POST /revisao/{video_id}/rejeitar` | Rejeitar roteiro | Alta |
| `GET /gameplay/segmentos` | Listar segmentos gameplay | Média |
| `GET /gameplay/estatisticas` | Estatísticas por jogo | Média |
| `GET /nichos` | Listar configurações de nichos | Média |
| `PUT /nichos/{nicho}` | Editar configuração de nicho | Baixa |
| `GET /gameplay/crop-config` | Listar configs de crop | Média |
| `PUT /gameplay/crop-config/{jogo}` | Editar crop config | Baixa |
| `GET /gpu-status` | Status do GPU lock | Média |
| `GET /tendencias/fontes-status` | Status das fontes | Baixa |

---

## 2. Comandos CLI (`main.py`)

### 2.1 Comandos Existentes

| Comando | Ação | Endpoint Equivalente |
|---------|------|---------------------|
| `--run-once` | Executa pipeline uma vez | Nenhum (internos) |
| `--listar-falhas` | Lista execuções falhas | `GET /execucoes?status=falha` |
| `--retomar VIDEO_ID` | Retoma execução falha | **FALTA** endpoint |
| `--listar-pendentes` | Lista roteiros pendentes | **FALTA** endpoint |
| `--revisar VIDEO_ID --aprovar` | Aprova roteiro | **FALTA** endpoint |
| `--revisar VIDEO_ID --rejeitar` | Rejeita roteiro | **FALTA** endpoint |
| `--sugerir-ideia` | Cria ideia manual | `POST /ideias-manuais` |
| `--listar-ideias-manuais` | Lista ideias manuais | `GET /ideias-manuais` |
| `--descartar-ideia ID` | Descarta ideia manual | `DELETE /ideias-manuais/{id}` |
| `--ingerir-gameplay` | Ingere gameplay bruta | Nenhum (CLI only) |
| `--listar-gameplay` | Lista segmentos gameplay | **FALTA** endpoint |
| `--custos` | Relatório de custos LLM | **FALTA** endpoint |
| `--metadata VIDEO_ID` | Gera metadata | `GET /execucoes/{video_id}/metadata` |

### 2.2 Lógica de Retomada

A função `retomar_execucao_falha(video_id)` já existe em `pipeline/orchestrator.py`:
- Busca execução falha no banco
- Identifica etapa em que parou
- Carrega roteiro (se existir)
- Continua a partir da fase correta
- Registra sucesso/falha no banco

**Implementação:** Reaproveitar esta função, não duplicar.

---

## 3. Tabelas do Banco (`db/models.py`)

### 3.1 Tabelas Relevantes para Frontend

**`dados.videos_ideias`** — Ideias geradas:
```python
id: int (PK, autoincrement)
topico: str
titulo_sugerido: str
descricao_breve: str?
nicho: str (default: "cultura_pop")
status: str (default: "pendente")
data_criacao: datetime
embedding: str?  # Para duplicidade semântica
```

**`dados.roteiros`** — Roteiros completos:
```python
id: int (PK, autoincrement)
video_id: str (unique, indexed)
nicho: str
titulo_sugerido: str
payload_json: str  # Roteiro completo serializado
status_revisao: str (default: "pendente")  # pendente, aprovado, rejeitado
revisado_em: datetime?
criado_em: datetime
```

**`dados.execucoes_pipeline`** — Histórico de execuções:
```python
id: int (PK, autoincrement)
video_id: str
nicho: str
etapa_atual: str (default: "ideacao")
sucesso: bool?
caminho_video_final: str?
wer_medio: float?
motivo_falha: str?
criado_em: datetime
```

**`dados.ideias_manuais`** — Ideias injetadas pelo usuário:
```python
id: int (PK, autoincrement)
nicho: str (indexed)
titulo_sugerido: str
descricao_breve: str?
tendencia_relacionada: str?
prioridade: str (default: "normal")  # alta, normal
status: str (default: "pendente")  # pendente, usada, descartada
video_id: str?
criado_em: datetime
```

**`dados.gameplay_segmentos`** — Segmentos de gameplay indexados:
```python
id: int (PK, autoincrement)
jogo_origem: str (indexed)
caminho_arquivo: str (unique)
duracao_segundos: float
score_movimento: float
faixa_intensidade: str  # calmo, moderado, intenso
hash_conteudo: str(32) (unique)  # MD5
usado_em: list[str]?  # video_ids com timestamp
criado_em: datetime
```

### 3.2 Funções Helper Disponíveis

**Em `db/models.py`:**
- `listar_roteiros_pendentes_revisao(limite)` → Expõe via endpoint
- `atualizar_status_revisao(video_id, status)` → Expõe via endpoint
- `listar_execucoes_falhas(limite)` → Já exposto via `GET /execucoes?status=falha`
- `buscar_execucao_falha(video_id)` → Usado pela lógica de retomada
- `salvar_execucao(...)` → Usado pela lógica de retomada
- `buscar_gameplay_segmentos(...)` → Expõe via endpoint
- `salvar_gameplay_segmentos(...)` → Interno, não expor
- `marcar_gameplay_usado(...)` → Interno, não expor

---

## 4. Configuração de Nichos (`pipeline/nichos.py`)

### 4.1 Estrutura `ConfigNicho`

```python
class ConfigNicho(NamedTuple):
    nome: str
    prompt_ideacao: str
    prompt_roteiro_adicional: str
    prompt_roteiro_short: str
    categoria_google_trends: int
    subreddits_sugeridos: list[str]
    gameplay_intensidade_preferida: str = "moderado"
    pitch_shift_semitons: float | None = None  # -2.0 a +2.0
    velocidade_fala: float | None = None  # 0.95 a 1.05
```

### 4.2 Nichos Configurados

| Nicho | Categoria GT | Subreddits | Timbre | Gameplay |
|-------|--------------|------------|--------|----------|
| `cultura_pop` | 22 (Entertainment) | r/anime, r/movies, r/gaming | Determinístico | moderado |
| `tecnologia` | 5 (Technology) | r/technology, r/programming | Determinístico | moderado |
| `futebol` | 20 (Sports) | r/soccer, r/football | Determinístico | moderado |
| `financas` | 7 (Finance) | r/personalfinance, r/investing | Determinístico | moderado |
| `ciencia` | 11 (Science) | r/science, r/space | Determinístico | moderado |
| `historia` | 24 (Society) | r/history, r/AskHistorians | Determinístico | moderado |

### 4.3 Funções Disponíveis

- `obter_config_nicho(nicho)` → Retorna config
- `listar_nichos_disponiveis()` → Retorna lista de nomes

**Decisão:** Configuração de nicho está hardcoded em Python, não em banco. Editar via UI requer:
1. Opção A: Mover config para banco (mais complexo, hot-reload)
2. Opção B: Manter em Python, edição limitada via UI requer restart

---

## 5. Configuração de Crop por Jogo (`services/gameplay/crop_config.py`)

### 5.1 Estrutura `CropConfigJogo`

```python
class CropConfigJogo(NamedTuple):
    jogo: str
    crop_offset_y: int  # -500 a +500 pixels
    descricao: str = ""
```

### 5.2 Jogos Configurados

| Jogo | Offset Y | Descrição |
|------|-----------|-----------|
| minecraft | 0 | Centrado |
| fortnite | -50 | Acima (evitar HUD baixa) |
| valorant | 100 | Abaixo (minimap topo) |
| league_of_legends | 150 | Mais abaixo (minimap) |
| gta_v | -80 | Acima (minimap inferior) |
| call_of_duty | 0 | Centrado |
| apex_legends | 50 | Abaixo (HUD superior) |
| dota_2 | 150 | Mais abaixo (minimap) |
| csgo | 0 | Centrado |
| free_fire | -30 | Acima (controles mobile) |

### 5.3 Funções Disponíveis

- `obter_crop_offset_y(jogo, default)` → Retorna offset
- `listar_jogos_configurados()` → Retorna lista de nomes

**Decisão:** Configuração está hardcoded, mesma situação que nichos.

---

## 6. GPU Lock (`pipeline/gpu_lock.py`)

### 6.1 Implementação Atual

```python
_gpu_semaphore = asyncio.Semaphore(1)

@asynccontextmanager
async def gpu_task(task_name: str):
    # Log wait/start/finish
    async with _gpu_semaphore:
        yield
```

### 6.2 Status não Exposto

**Falta:** Endpoint para verificar se GPU está ocupada/livre.

**Necessário:** Criar função helper que expõe estado do semaphore:
```python
def gpu_status() -> dict:
    return {
        "disponivel": _gpu_semaphore.locked() == False,
        "tarefas_em_espera": ?,  # Difícil de extrair
    }
```

---

## 7. Segurança — Configuração Atual

### 7.1 FastAPI

O arquivo `api/status.py` não configura explicitamente:
- Bind address (depende de como uvicorn é chamado)
- CORS
- Autenticação

### 7.2 Docker Compose

O `docker-compose.yml` não expõe a API HTTP — ela não é executada como serviço.

### 7.3 main.py

O `main.py` executa o pipeline via CLI ou scheduler, não inicia o servidor FastAPI.

**Para iniciar o servidor:**
```bash
cd api && python status.py  # Inicia uvicorn
# ou
uvicorn api.status:app --host 127.0.0.1 --port 8000
```

---

## 8. Lacunas Identificadas (Checklist)

### 8.1 Backend

- [ ] Bind FastAPI em `127.0.0.1` (não `0.0.0.0`)
- [ ] Configurar CORS para frontend local
- [ ] Endpoint `POST /execucoes/{video_id}/retomar`
- [ ] Endpoints de revisão: `GET /revisao/pendentes`, `POST /revisao/{id}/aprovar`, `POST /revisao/{id}/rejeitar`
- [ ] Endpoint `GET /gameplay/segmentos`
- [ ] Endpoint `GET /gameplay/estatisticas`
- [ ] Endpoint `GET /nichos`
- [ ] Endpoint `GET /gpu-status`
- [ ] Endpoint `GET /tendencias/fontes-status` (opcional, baixa prioridade)

### 8.2 Decisões de Design Necessárias

1. **Edição de nichos via UI:**
   - Opção A: Mover `NICHOS_CONFIG` para banco
   - Opção B: Manter em Python, só visualização na UI
   - Recomendação: Opção B para primeira versão

2. **Edição de crop config via UI:**
   - Opção A: Mover `CROP_CONFIG_POR_JOGO` para banco
   - Opção B: Manter em Python, só visualização
   - Recomendação: Opção B para primeira versão

3. **NICHOS_ATIVOS no .env:**
   - Opção A: Manter em .env (requer restart)
   - Opção B: Mover para banco (hot-reload)
   - Recomendação: Manter em .env, documentar necessidade de restart

---

## 9. Próximos Passos

1. **Backend — Segurança e CORS:**
   - Criar arquivo `api/main.py` que configura FastAPI com CORS e bind
   - Adicionar script para iniciar servidor em `127.0.0.1`

2. **Backend — Novos Endpoints:**
   - Implementar endpoints faltantes (seção 8.1)
   - Seguir padrão existente em `api/status.py`

3. **Frontend — Setup:**
   - Criar projeto Vite + React + TypeScript
   - Configurar Tailwind + shadcn/ui
   - Configurar TanStack Query
   - Criar tipos TypeScript espelhando schemas Pydantic

4. **Frontend — Telas:**
   - Seguir ordem da seção 8 do prompt original

---

## 10. Resumo

**Endpointbase existente:** 7 endpoints
**Endpointbase faltante:** ~8 endpoints
**Tabelas relevantes:** 5 tabelas
**Nichos configurados:** 6
**Jogos com crop config:** 10
**Decisões pendentes:** 3 (config em banco vs Python)

**Estado:** Backend funcional para operação via CLI, faltam endpoints e configurações de segurança para suportar frontend web.
