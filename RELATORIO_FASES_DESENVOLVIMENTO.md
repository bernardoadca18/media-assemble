
# Relatório de Planejamento — Fases de Desenvolvimento
## Sistema Autônomo de Vídeos Faceless (100% Python)

**Documento:** Planejamento técnico de fases de implementação
**Base de referência:** Guia de Arquitetura e Implementação (documento anterior) + `faceless-pipeline-base.zip` (esqueleto de código entregue junto a este relatório)
**Execução:** Agente de programação (OpenClaude, modelo GLM-5)

---

## 1. Premissas e Metodologia

Este planejamento assume:

- **Desenvolvimento incremental e testável por fase.** Cada fase produz um artefato que pode ser executado e validado isoladamente, sem depender das fases seguintes ainda não implementadas. Isso é essencial ao delegar a implementação a um agente de IA: cada fase precisa ter critério de aceite objetivo e verificável, não apenas "parece pronto".
- **A base entregue (`faceless-pipeline-base.zip`) já resolve a Fase 0 (Fundação).** Ela contém a estrutura de diretórios completa, configuração via `.env`, o `gpu_lock` (peça crítica de concorrência), os schemas Pydantic que servem de contrato entre todas as etapas, e uma implementação de referência da Fase 1 (Tendências + Ideação) já funcional e testável — o agente não parte do zero, parte de uma espinha dorsal validada.
- **Ordem das fases segue a ordem real do pipeline de dados** (tendência → ideia → roteiro → áudio → visual → render → orquestração), o que minimiza retrabalho: cada fase consome exatamente o output validado da fase anterior.
- **Cada fase deve terminar com o repositório em estado funcional e commitável** — nunca com código quebrado ou testes falhando propositalmente para "continuar depois".

### Convenção de nomenclatura das fases

Para evitar confusão com a "Fase 1" mencionada tecnicamente no código-base entregue (que já vem parcialmente implementada), este relatório numera as fases de desenvolvimento de forma sequencial e explícita, reafirmando o escopo de cada uma.

---

## 2. Visão Geral das Fases

| Fase | Nome | Entrega principal | Depende de |
|---|---|---|---|
| 0 | Fundação (**já entregue**) | Esqueleto do projeto, config, schemas, GPU lock, DB, LiteLLM client | — |
| 1 | Tendências & Ideação | Pipeline de coleta → normalização → ideação → persistência, 100% funcional e testado | Fase 0 |
| 2 | Roteirização | Agente que expande uma ideia aprovada no JSON de roteiro completo | Fase 1 |
| 3 | Pipeline de Áudio | F5-TTS + Faster-Whisper + validação WER + concatenação FFmpeg | Fase 2 |
| 4 | Assets Visuais | Resolução via banco local + fallback externo licenciado | Fase 2 (paralelizável com Fase 3) |
| 5 | Renderização (Remotion) | Projeto Remotion completo + ponte Python via subprocess | Fases 3 e 4 |
| 6 | Orquestração End-to-End | Pipeline completo automatizado, agendado, com rastreabilidade e observabilidade | Fases 1–5 |
| 7 | Hardening & Escala | Multi-nicho, testes automatizados abrangentes, deploy/ops, monitoramento de custo de API | Fase 6 |

As Fases 3 e 4 podem, na prática, ser desenvolvidas em paralelo por não terem dependência direta entre si (ambas dependem apenas do roteiro gerado na Fase 2) — mas recomenda-se sequenciar mesmo assim se o desenvolvimento for feito por um único agente de cada vez, para manter o foco e reduzir a superfície de contexto por sessão.

---

## 3. Detalhamento por Fase

### Fase 0 — Fundação (já entregue nesta base)

**Status:** Concluída. Não requer ação do agente além de leitura/familiarização.

**Conteúdo entregue:**
- Estrutura de diretórios completa (`pipeline/`, `services/`, `db/`, `utils/`, `remotion/`, `data/`, `tests/`).
- `pipeline/config.py`: configuração centralizada via `.env` (Pydantic Settings).
- `pipeline/schemas.py`: contrato de dados completo — `Ideia`, `RespostaIdeacao`, `Roteiro`, `Cena`, `Midia`, `EfeitosVisuais`, `Overlays`, `Palavra`. **Este arquivo é a fonte da verdade estrutural do projeto**; qualquer alteração de formato de dados nas fases seguintes deve começar por uma alteração consciente aqui.
- `pipeline/gpu_lock.py`: semáforo global de GPU, já funcional.
- `utils/litellm_client.py`: cliente unificado para modelos locais (com `gpu_lock`) e modelos em nuvem (sem lock).
- `db/models.py` e `db/session.py`: modelos SQLAlchemy (`VideoIdeia`, `ExecucaoPipeline`) e sessão assíncrona.
- `services/trends/` e `services/ideation/`: implementação de referência funcional (ver Fase 1 abaixo).
- Stubs documentados (`NotImplementedError` + docstring apontando a fase responsável) para todos os módulos das Fases 2 a 5.
- `tests/test_schemas.py`: teste de sanidade inicial.
- `README.md`: guia de setup e visão geral.

---

### Fase 1 — Tendências & Ideação

> **Esta é a fase a ser desenvolvida agora pelo agente**, a partir da base entregue. Ver seção 5 deste relatório para o prompt de contextualização completo.

**Objetivo:** Deixar 100% funcional, testado e persistindo dados reais no Postgres o trecho do pipeline equivalente ao antigo fluxo n8n `Scrapper` — da coleta de tendências até a geração e persistência de 5 ideias de vídeo por execução.

**Escopo técnico:**
1. Implementar `services/trends/scraper.py` com ao menos **uma fonte real** de tendências (recomendação: Google Trends via biblioteca `pytrends`, por não exigir credenciais de API pagas). As demais fontes (Reddit, YouTube trending) podem permanecer como stubs anotados, desde que não quebrem o pipeline.
2. Validar/ajustar `services/trends/normalizer.py` (já usa o `complete_local` da Fase 0) contra a saída real do scraper implementado.
3. Implementar a consulta real em `services/ideation/rag_client.py::buscar_titulos_recentes`, usando `db/models.py::buscar_titulos_recentes_db` (já implementado na base) — este ponto já está praticamente pronto, é conectar a chamada.
4. Validar `services/ideation/agent.py` (prompt já migrado do n8n) contra um modelo real via LiteLLM configurado no `.env`.
5. Configurar Alembic (`db/migrations/`) e gerar a migration inicial criando o schema `dados` e a tabela `videos_ideias` (compatível com a estrutura já existente, caso o usuário for reaproveitar o banco atual do n8n) e a tabela `execucoes_pipeline`.
6. Escrever testes automatizados cobrindo: parsing de resposta do LLM (casos válido e malformado), persistência no banco (pode usar banco de testes/SQLite em memória ou um Postgres de teste via `pytest` fixtures), e o fluxo `rodar_etapa_ideacao` ponta-a-ponta com mocks do LLM.

**Critérios de aceite:**
- `python main.py --run-once` executa sem erros e persiste 5 ideias válidas no Postgres para o nicho configurado no `.env`.
- Rodar a mesma execução uma segunda vez não deve gerar títulos idênticos aos da execução anterior (validação manual observando o histórico consultado no prompt).
- `pytest` roda verde para todos os testes da Fase 1.
- Nenhum `NotImplementedError` remanescente dentro do escopo desta fase (`services/trends/`, `services/ideation/`, persistência).

**Fora de escopo desta fase (não implementar ainda):** roteirização, áudio, visual, render — permanecem como stubs.

---

### Fase 2 — Roteirização

**Objetivo:** Dada uma `Ideia` já persistida (ou selecionada manualmente para testes), gerar um objeto `Roteiro` completo, validado pelo schema Pydantic existente, pronto para alimentar as Fases 3 e 4.

**Escopo técnico:**
1. Implementar `services/scripting/writer_agent.py::gerar_roteiro`, usando o System Prompt já especificado no guia de arquitetura (seção 5) — adaptar para receber a `Ideia` e a duração-alvo como parâmetros.
2. Implementar parsing e validação da resposta do LLM diretamente contra `pipeline.schemas.Roteiro` (mesma estratégia de robustez usada na Fase 1 com `RespostaIdeacao`).
3. Implementar lógica de retry com prompt de correção caso o JSON retornado falhe a validação Pydantic (ex: reenviar ao LLM o erro de validação e pedir correção, até um limite de tentativas).
4. Persistir o roteiro gerado (nova tabela `roteiros` ou armazenamento em disco como JSON versionado por `video_id` — decisão de design a documentar no PR).
5. Conectar `pipeline/orchestrator.py::rodar_pipeline_completo` para, após a ideação, chamar `gerar_roteiro` com a primeira ideia da lista.

**Critérios de aceite:**
- Dada uma ideia de exemplo fixa (fixture de teste), o agente gera um `Roteiro` válido em pelo menos 8 de 10 execuções (tolerância a falhas ocasionais de formatação do LLM, cobertas pelo retry).
- Testes cobrindo: validação de schema, lógica de retry em caso de JSON malformado, e a integração com o orchestrator.

---

### Fase 3 — Pipeline de Áudio

**Objetivo:** Transformar cada `texto_locucao` do roteiro em áudio validado, com timestamps por palavra, e produzir o áudio master concatenado.

**Escopo técnico:**
1. Implementar `services/audio/tts_engine.py` (wrapper F5-TTS, protegido por `gpu_task`) — especificação completa na seção 3.2 do guia de arquitetura.
2. Implementar `services/audio/validator.py` (Faster-Whisper + cálculo de WER via distância de Levenshtein) — seção 3.3 do guia.
3. Implementar `services/audio/mixer.py` (concatenação via FFmpeg concat demuxer) — seção 3.5 do guia.
4. Implementar o loop de geração/validação/retry por seed (equivalente a `pipeline_audio.py::gerar_e_validar_cena` do guia), populando `Cena.audio_path`, `Cena.palavras_transcritas`, `Cena.wer_final` e `Cena.revisao_manual_necessaria`.
5. Conectar ao orchestrator, após a Fase 2.
6. **Ponto crítico de teste manual:** validar em hardware real que o `gpu_lock` está de fato serializando as chamadas ao F5-TTS e ao Whisper — rodar duas cenas "simultaneamente" (sem lock, como teste negativo) e confirmar que sem o lock ocorre erro de OOM ou degradação, e com o lock não ocorre.

**Critérios de aceite:**
- Rodar o pipeline de áudio sobre um roteiro de teste (5–8 cenas) sem estourar VRAM.
- WER médio das cenas aprovadas abaixo do limiar configurado (`WER_LIMITE_APROVACAO` no `.env`).
- Áudio master final concatenado sem cortes, cliques ou silêncios anômalos entre cenas (validação auditiva manual).

---

### Fase 4 — Assets Visuais

**Objetivo:** Popular `Cena.asset_resolvido_path` para cada cena do roteiro, priorizando o banco local e usando fallback externo apenas quando necessário.

**Escopo técnico:**
1. Implementar `services/visual/asset_resolver.py`: estratégia de busca no banco local (`data/assets_local/`) — recomenda-se um índice simples (JSON ou tabela no Postgres) mapeando tags → caminhos de arquivo, populado manualmente pelo usuário ou por um script auxiliar de indexação.
2. Implementar `services/visual/fallback_scraper.py` com **apenas fontes licenciadas para uso comercial** (Pexels API é a recomendação principal, já com variável `PEXELS_API_KEY` prevista no `.env.example`). `yt-dlp` deve ser implementado por último e tratado como último recurso, conforme a seção 4 do guia de arquitetura.
3. Definir e documentar a política de fallback: quantas tentativas de busca por keyword antes de cair para `fallback_query`, e o que acontece se nenhum asset for encontrado (bloquear a cena para revisão manual, nunca deixar a cena sem asset silenciosamente).

**Critérios de aceite:**
- Roteiro de teste com cenas cujas keywords existem no banco local resolve 100% localmente, sem chamadas externas.
- Roteiro de teste com keywords propositalmente ausentes do banco local aciona corretamente o fallback e resolve via Pexels.
- Nenhuma cena termina o processamento sem `asset_resolvido_path` preenchido ou sinalizada explicitamente para revisão manual.

---

### Fase 5 — Renderização (Remotion)

**Objetivo:** Projeto Remotion funcional, renderizando o vídeo final a partir do roteiro totalmente populado (áudio + assets + legendas), disparado via `subprocess` a partir do Python.

**Escopo técnico:**
1. Inicializar o projeto Remotion de fato (`npx create-video@latest` dentro de `remotion/`, ou instalação manual das dependências já listadas em `remotion/package.json`).
2. Implementar os componentes já especificados no guia de arquitetura (seção 2): `KenBurnsImage.tsx`, `SubtitlesOverlay.tsx`, `AudioTrack.tsx`, `SceneRenderer.tsx`, `VideoComposition.tsx`, `Root.tsx` (substituindo o placeholder atual).
3. Implementar `services/render/remotion_bridge.py::renderizar_video` (seção 2.8 do guia) — serialização do roteiro para arquivo temporário + chamada `subprocess` com `--concurrency=1`.
4. Conectar ao orchestrator como etapa final do pipeline.
5. Testar renderização de um vídeo completo de ponta a ponta usando dados reais das Fases 1–4.

**Critérios de aceite:**
- `npx remotion render` executa sem erros a partir do payload gerado pelo Python.
- Vídeo final gerado com áudio sincronizado, legendas dinâmicas corretas (timestamps batendo com a narração) e efeito Ken Burns visivelmente aplicado.
- Duração do vídeo final compatível com a soma das durações das cenas (tolerância de poucos frames por arredondamento).

---

### Fase 6 — Orquestração End-to-End, Agendamento e Observabilidade

**Objetivo:** Unir todas as fases anteriores em um pipeline verdadeiramente autônomo, agendado, com rastreabilidade completa de cada execução.

**Escopo técnico:**
1. Finalizar `pipeline/orchestrator.py::rodar_pipeline_completo` encadeando as 5 etapas sem intervenção manual.
2. Implementar `db/models.py::salvar_execucao` (atualmente `NotImplementedError`), registrando cada execução completa (`ExecucaoPipeline`): etapa atual, sucesso/falha, caminho do vídeo final, WER médio.
3. Implementar tratamento de erro por etapa: se uma etapa falhar (ex: nenhum asset encontrado para uma cena crítica), a execução deve ser marcada como falha na tabela `execucoes_pipeline` com a etapa e o motivo, **sem derrubar o processo agendado** — a próxima execução do `APScheduler` deve continuar normalmente.
4. Adicionar logging estruturado (já preparado em `utils/logger.py`) em todas as etapas, com `video_id` como campo correlacionador em todos os logs de uma mesma execução.
5. (Opcional, recomendado) Endpoint HTTP simples (FastAPI) apenas para consulta de status de execuções — não é necessário reintroduzir webhook de disparo, já que o `APScheduler` cobre o agendamento.

**Critérios de aceite:**
- Pipeline completo roda de forma autônoma via `python main.py` (modo agendado) por múltiplos ciclos sem intervenção manual.
- Uma falha proposital em uma etapa intermediária (ex: renomear temporariamente a chave de API do Pexels) não derruba o scheduler nem corrompe o estado do banco.
- É possível reconstruir o histórico completo de qualquer execução (sucesso ou falha) consultando `execucoes_pipeline`.

---

### Fase 7 — Hardening, Multi-Nicho e Operação Contínua

**Objetivo:** Preparar o sistema para operação de longo prazo, com múltiplos nichos simultâneos e monitoramento de custo.

**Escopo técnico:**
1. Validar e ajustar o pipeline para rodar múltiplos nichos configurados (`NICHOS_ATIVOS` no `.env`) sem colisão de recursos — especialmente o `gpu_lock`, que deve continuar serializando corretamente mesmo com múltiplos nichos agendados.
2. Cobertura de testes automatizados ampliada para todas as fases (meta sugerida: cobrir os principais caminhos felizes e os principais caminhos de falha de cada `service`).
3. Monitoramento de custo de chamadas a modelos em nuvem (contagem de tokens/custo estimado por execução, logado em `execucoes_pipeline` ou tabela dedicada).
4. Rotina de limpeza de arquivos temporários (`data/audio_temp/`) após renderização bem-sucedida, com política de retenção configurável.
5. Documentação operacional final (runbook): como reiniciar o serviço, como diagnosticar uma execução falha, como adicionar um novo nicho.

**Critérios de aceite:**
- Sistema roda de forma estável por um período de teste prolongado (ex: 1 semana) com múltiplos nichos ativos.
- Custo de API por vídeo gerado é visível e auditável.
- Onboarding de um novo nicho documentado e testado por alguém que não seja o desenvolvedor original.

---

## 4. Riscos e Pontos de Atenção Transversais

- **GPU como recurso único é o maior risco de instabilidade.** Todas as fases que tocam GPU (1 parcialmente, 3 integralmente, 5 indiretamente via Remotion/Chrome headless) devem ser testadas em hardware real antes de serem consideradas concluídas — testes com mocks não capturam problemas de VRAM.
- **Qualidade da resposta do LLM é não-determinística.** Toda etapa que depende de JSON estruturado gerado por LLM (Fases 1, 2) precisa de estratégia de retry/correção — já prevista na base entregue e reforçada nas fases correspondentes.
- **Licenciamento de assets é responsabilidade de design, não apenas de implementação.** A Fase 4 deve ser revisada com atenção especial às fontes usadas em produção, conforme já discutido na seção 4 do guia de arquitetura.
- **Migração de dados do banco atual (n8n) para o novo schema**, se aplicável, deve ser tratada como uma tarefa explícita na Fase 1 (script de migração único), não deixada implícita.

---

## 5. Ver também

O prompt de contextualização para o agente de programação (OpenClaude / GLM-5), correspondente à **Fase 1**, está no arquivo separado `PROMPT_OPENCLAUDE_FASE1.md`, entregue junto a este relatório.
