# Frontend - Faceless Pipeline

Interface de gestão para o Faceless Pipeline, construída com React 18 + TypeScript + Vite.

## Tecnologias

- **React 18** - Framework UI
- **TypeScript** - Tipagem estática
- **Vite** - Build tool e dev server
- **TanStack Query** - Data fetching e cache
- **React Router** - Roteamento SPA
- **Tailwind CSS v3** - Estilização com CSS variables

## Setup

```bash
# Instalar dependências
npm install

# Desenvolvimento
npm run dev

# Build para produção
npm run build

# Preview do build
npm run preview
```

## Estrutura

```
src/
├── api/
│   └── client.ts          # Cliente HTTP para API backend
├── components/
│   └── Layout.tsx         # Layout principal com navegação
├── hooks/
│   └── useAPI.ts          # TanStack Query hooks
├── lib/
│   └── utils.ts           # Utilitários (cn para classes)
├── pages/
│   ├── Dashboard.tsx      # Visão geral do pipeline
│   ├── Execucoes.tsx      # Histórico de execuções
│   ├── Revisao.tsx        # Revisão manual de roteiros
│   ├── IdeiasManuais.tsx  # Gerenciamento de ideias
│   ├── Gameplay.tsx       # Segmentos de gameplay
│   └── Nichos.tsx         # Configurações de nicho
├── types/
│   └── api.ts             # TypeScript types (Pydantic mirrors)
├── App.tsx                # Rotas principais
├── main.tsx               # Entry point
└── index.css              # Tailwind + CSS variables
```

## Páginas

### Dashboard (`/`)
- Status da GPU (disponível/ocupada)
- Estatísticas de execuções (total, sucesso, falhas)
- Execuções recentes

### Execuções (`/execucoes`)
- Listagem de todas as execuções
- Filtro por status (sucesso/falha)
- Botão de retomar para execuções falhas

### Revisão Manual (`/revisao`)
- Roteiros pendentes de aprovação
- Aprovar/Rejeitar roteiros

### Ideias Manuais (`/ideias-manuais`)
- Criar novas ideias de vídeo
- Prioridade alta (substitui vaga no lote) ou normal
- Listar ideias existentes

### Gameplay (`/gameplay`)
- Estatísticas por jogo
- Tabela de segmentos indexados
- Filtros por jogo e intensidade

### Nichos (`/nichos`)
- Configurações de todos os nichos
- Subreddits sugeridos
- Preferências de gameplay e TTS

## Backend API

O frontend consome a API FastAPI em `http://127.0.0.1:8000`.

Para iniciar o backend:

```bash
uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
```

## Segurança

- API bind apenas em `127.0.0.1` (localhost)
- CORS restrito a `localhost:5173` e `localhost:3000`
- Sem autenticação (uso local)

## Scripts

| Comando | Descrição |
|---------|-----------|
| `npm run dev` | Inicia dev server (porta 5173) |
| `npm run build` | Build de produção |
| `npm run preview` | Preview do build |
| `npm run lint` | Lint com oxlint |
