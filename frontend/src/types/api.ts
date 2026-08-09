// Types mirroring Pydantic schemas from api/main.py and api/status.py

// Health check
export interface HealthStatus {
  status: string
  timestamp: string
}

// GPU Status
export interface GPUStatus {
  disponivel: boolean
  mensagem: string
}

// Execuções (from api/status.py)
export interface ExecucaoResumo {
  video_id: string
  nicho: string
  etapa_atual: string
  sucesso: boolean | null
  motivo_falha: string | null
  criado_em: string
}

export interface ExecucaoDetalhe {
  video_id: string
  nicho: string
  etapa_atual: string
  sucesso: boolean | null
  caminho_video_final: string | null
  wer_medio: number | null
  motivo_falha: string | null
  criado_em: string
}

export interface RetomarResposta {
  sucesso: boolean
  video_id: string
  mensagem: string
  etapa_retomada: string | null
}

// Revisão Manual (from api/main.py)
export interface RoteiroPendente {
  video_id: string
  nicho: string
  titulo_sugerido: string
  criado_em: string
}

export interface RevisaoResposta {
  sucesso: boolean
  video_id: string
  novo_status: string
  mensagem: string
}

// Gameplay
export interface SegmentoGameplay {
  id: number
  jogo_origem: string
  caminho_arquivo: string
  duracao_segundos: number
  score_movimento: number
  faixa_intensidade: string
  usado_em: string[]
  criado_em: string
}

export interface EstatisticasGameplay {
  jogo: string
  total_segmentos: number
  duracao_total_segundos: number
  duracao_total_formatada: string
  aprovados: number
  rejeitados: number
  taxa_aprovacao: number
}

// Nichos
export interface NichoConfig {
  nome: string
  categoria_google_trends: number
  subreddits_sugeridos: string[]
  gameplay_intensidade_preferida: string
  prompt_roteiro_short_configurado: boolean
  timbre_pitch_shift: number | null
  timbre_velocidade: number | null
}

export interface NichoCreate {
  nome: string
  prompt_ideacao: string
  prompt_roteiro_adicional: string
  prompt_roteiro_short: string
  categoria_google_trends: number
  subreddits_sugeridos: string[]
  gameplay_intensidade_preferida?: string
  timbre_pitch_shift?: number | null
  timbre_velocidade?: number | null
}

export interface NichoUpdate {
  prompt_ideacao?: string
  prompt_roteiro_adicional?: string
  prompt_roteiro_short?: string
  categoria_google_trends?: number
  subreddits_sugeridos?: string[]
  gameplay_intensidade_preferida?: string
  timbre_pitch_shift?: number | null
  timbre_velocidade?: number | null
  ativo?: boolean
}

// Metadata Publicação (from api/status.py)
export interface MetadataPublicacao {
  titulos: string[]
  descricao: string
  tags: string[]
  playlist_sugerida: string
  playlist_nova: boolean
}

// Ideias Manuais (from api/status.py)
export interface IdeiaManual {
  id: number
  nicho: string
  titulo_sugerido: string
  descricao_breve: string | null
  tendencia_relacionada: string | null
  prioridade: string
  status: string
  video_id: string | null
  criado_em: string
}

export interface IdeiaManualCreate {
  nicho: string
  titulo_sugerido: string
  descricao_breve?: string
  tendencia_relacionada?: string
  prioridade?: 'alta' | 'normal'
}

// Dashboard stats (aggregated)
export interface DashboardStats {
  execucoes_hoje: number
  execucoes_semana: number
  execucoes_falhas: number
  execucoes_sucesso: number
  roteiros_pendentes: number
  gpu_disponivel: boolean
}
