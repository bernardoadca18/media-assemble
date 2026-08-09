import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import * as api from '../api/client'

// Health
export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: api.healthCheck,
    refetchInterval: 30000, // Check every 30s
  })
}

// GPU Status
export function useGPUStatus() {
  return useQuery({
    queryKey: ['gpu-status'],
    queryFn: api.getGPUStatus,
    refetchInterval: 10000, // Check every 10s
  })
}

// Execuções
export function useExecucoes(params?: { status?: string; limite?: number }) {
  return useQuery({
    queryKey: ['execucoes', params],
    queryFn: () => api.listarExecucoes(params),
  })
}

export function useExecucao(videoId: string) {
  return useQuery({
    queryKey: ['execucao', videoId],
    queryFn: () => api.obterExecucao(videoId),
    enabled: !!videoId,
  })
}

export function useRetomarExecucao() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.retomarExecucao,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['execucoes'] })
      queryClient.invalidateQueries({ queryKey: ['execucao'] })
    },
  })
}

// Revisão
export function usePendentesRevisao(limite?: number) {
  return useQuery({
    queryKey: ['revisao-pendentes', limite],
    queryFn: () => api.listarPendentesRevisao(limite),
  })
}

export function useAprovarRoteiro() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.aprovarRoteiro,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revisao-pendentes'] })
      queryClient.invalidateQueries({ queryKey: ['execucoes'] })
    },
  })
}

export function useRejeitarRoteiro() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.rejeitarRoteiro,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['revisao-pendentes'] })
      queryClient.invalidateQueries({ queryKey: ['execucoes'] })
    },
  })
}

// Gameplay
export function useSegmentosGameplay(params?: { jogo?: string; intensidade?: string; limite?: number }) {
  return useQuery({
    queryKey: ['gameplay-segmentos', params],
    queryFn: () => api.listarSegmentosGameplay(params),
  })
}

export function useEstatisticasGameplay() {
  return useQuery({
    queryKey: ['gameplay-estatisticas'],
    queryFn: api.listarEstatisticasGameplay,
  })
}

// Nichos
export function useNichos() {
  return useQuery({
    queryKey: ['nichos'],
    queryFn: api.listarNichos,
  })
}

export function useNicho(nome: string) {
  return useQuery({
    queryKey: ['nicho', nome],
    queryFn: () => api.obterNicho(nome),
    enabled: !!nome,
  })
}

export function useCriarNicho() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.criarNicho,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nichos'] })
    },
  })
}

export function useAtualizarNicho() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ nome, data }: { nome: string; data: import('../types/api').NichoUpdate }) =>
      api.atualizarNicho(nome, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nichos'] })
      queryClient.invalidateQueries({ queryKey: ['nicho'] })
    },
  })
}

export function useDeletarNicho() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.deletarNicho,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nichos'] })
    },
  })
}

// Metadata Publicação
export function useMetadataPublicacao(videoId: string) {
  return useQuery({
    queryKey: ['metadata', videoId],
    queryFn: () => api.obterMetadataPublicacao(videoId),
    enabled: !!videoId,
  })
}

// Ideias Manuais
export function useIdeiasManuais() {
  return useQuery({
    queryKey: ['ideias-manuais'],
    queryFn: api.listarIdeiasManuais,
  })
}

export function useCriarIdeiaManual() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: api.criarIdeiaManual,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ideias-manuais'] })
    },
  })
}
