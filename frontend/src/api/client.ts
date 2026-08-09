const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8080'

async function fetchAPI<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Erro desconhecido' }))
    throw new Error(error.detail || `HTTP ${response.status}`)
  }

  return response.json()
}

// Health
export const healthCheck = () => fetchAPI<import('../types/api').HealthStatus>('/health')

// GPU Status
export const getGPUStatus = () => fetchAPI<import('../types/api').GPUStatus>('/gpu-status')

// Execuções
export const listarExecucoes = (params?: { status?: string; limite?: number }) => {
  const query = new URLSearchParams()
  if (params?.status) query.set('status', params.status)
  if (params?.limite) query.set('limite', String(params.limite))
  const queryStr = query.toString()
  return fetchAPI<import('../types/api').ExecucaoResumo[]>(`/execucoes${queryStr ? `?${queryStr}` : ''}`)
}

export const obterExecucao = (videoId: string) =>
  fetchAPI<import('../types/api').ExecucaoDetalhe>(`/execucoes/${videoId}`)

export const retomarExecucao = (videoId: string) =>
  fetchAPI<import('../types/api').RetomarResposta>(`/execucoes/${videoId}/retomar`, { method: 'POST' })

// Revisão
export const listarPendentesRevisao = (limite?: number) => {
  const query = limite ? `?limite=${limite}` : ''
  return fetchAPI<import('../types/api').RoteiroPendente[]>(`/revisao/pendentes${query}`)
}

export const aprovarRoteiro = (videoId: string) =>
  fetchAPI<import('../types/api').RevisaoResposta>(`/revisao/${videoId}/aprovar`, { method: 'POST' })

export const rejeitarRoteiro = (videoId: string) =>
  fetchAPI<import('../types/api').RevisaoResposta>(`/revisao/${videoId}/rejeitar`, { method: 'POST' })

// Gameplay
export const listarSegmentosGameplay = (params?: { jogo?: string; intensidade?: string; limite?: number }) => {
  const query = new URLSearchParams()
  if (params?.jogo) query.set('jogo', params.jogo)
  if (params?.intensidade) query.set('intensidade', params.intensidade)
  if (params?.limite) query.set('limite', String(params.limite))
  const queryStr = query.toString()
  return fetchAPI<import('../types/api').SegmentoGameplay[]>(`/gameplay/segmentos${queryStr ? `?${queryStr}` : ''}`)
}

export const listarEstatisticasGameplay = () =>
  fetchAPI<import('../types/api').EstatisticasGameplay[]>('/gameplay/estatisticas')

// Nichos
export const listarNichos = () =>
  fetchAPI<import('../types/api').NichoConfig[]>('/nichos')

export const obterNicho = (nome: string) =>
  fetchAPI<import('../types/api').NichoConfig>(`/nichos/${nome}`)

export const criarNicho = (data: import('../types/api').NichoCreate) =>
  fetchAPI<import('../types/api').NichoConfig>('/nichos', {
    method: 'POST',
    body: JSON.stringify(data),
  })

export const atualizarNicho = (nome: string, data: import('../types/api').NichoUpdate) =>
  fetchAPI<import('../types/api').NichoConfig>(`/nichos/${nome}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })

export const deletarNicho = (nome: string) =>
  fetchAPI<{ mensagem: string }>(`/nichos/${nome}`, { method: 'DELETE' })

// Metadata Publicação
export const obterMetadataPublicacao = (videoId: string) =>
  fetchAPI<import('../types/api').MetadataPublicacao>(`/execucoes/${videoId}/metadata`)

// Ideias Manuais
export const listarIdeiasManuais = () =>
  fetchAPI<import('../types/api').IdeiaManual[]>('/ideias-manuais')

export const criarIdeiaManual = (data: import('../types/api').IdeiaManualCreate) =>
  fetchAPI<import('../types/api').IdeiaManual>('/ideias-manuais', {
    method: 'POST',
    body: JSON.stringify(data),
  })
