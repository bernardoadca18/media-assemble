# Remotion — Camada de Renderização (Fase 5)

Subprojeto Node.js/React responsável por renderizar o vídeo final a
partir do roteiro gerado pelo pipeline Python. Invocado via `subprocess`
por `services/render/remotion_bridge.py` — não é pensado para ser rodado
isoladamente em produção, mas é útil rodar `npm run start` durante o
desenvolvimento de componentes.

> Documentação geral do projeto (setup Python, banco de dados, status das
> fases) vive no `README.md` na raiz do repositório — este arquivo cobre
> só o que é específico deste subprojeto.

## Setup

```bash
cd remotion
npm install
```

## Comandos

```bash
npm run start   # Abre o Remotion Studio (preview interativo dos componentes)
npm run render  # Renderiza usando os defaultProps (útil para testar rapidamente)
```

Em produção, a renderização real é disparada pelo bridge Python
(`services/render/remotion_bridge.py::renderizar_video`), que monta o
comando `npx remotion render VideoPrincipal <saida> --props=<roteiro.json>`.

## Como os dados chegam até aqui

O bridge Python:
1. Copia os assets do roteiro (áudio da narração, imagens/vídeos de cada
   cena) para `public/`, com nomes únicos por `video_id`/`cena_id`.
2. Reescreve os paths desses assets no roteiro serializado para apontarem
   para os nomes de arquivo em `public/` (não mais paths absolutos do
   sistema de arquivos).
3. Serializa o roteiro inteiro (já com os paths reescritos) em um JSON
   temporário e passa via `--props=<caminho>`.

O Remotion CLI entrega o conteúdo desse arquivo **diretamente como objeto
de props** para `VideoComposition` (não é um caminho para outro arquivo)
— por isso os componentes usam `staticFile(path)` para resolver esses
nomes de arquivo relativos a `public/`, em vez de tentar ler o disco
diretamente.

## Estrutura dos componentes

```
src/
  Root.tsx                    # Registra a composição, calcula duração real via calculateMetadata
  index.ts                    # Entry point (registerRoot)
  components/
    VideoComposition.tsx      # Compõe todas as cenas + trilha de áudio
    SceneRenderer.tsx         # Renderiza uma cena (imagem/vídeo + overlays)
    KenBurnsImage.tsx         # Efeito de zoom/pan suave em imagens estáticas
    SubtitlesOverlay.tsx      # Legendas dinâmicas palavra-a-palavra
    AudioTrack.tsx            # Narração + trilha de fundo com ducking
```

## Status

Fase 5 implementada, mas **ainda sem validação de um render real
assistido de ponta a ponta** — ver `RELATORIO_FASES_DESENVOLVIMENTO.md`
e a auditoria mais recente na raiz do projeto antes de considerar esta
fase encerrada. O status agregado de todas as fases fica só no `README.md`
da raiz, para evitar duas fontes da verdade divergentes.
