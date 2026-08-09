import { usePendentesRevisao, useAprovarRoteiro, useRejeitarRoteiro } from '../hooks/useAPI'

export default function Revisao() {
  const { data: pendentes, isLoading } = usePendentesRevisao()
  const aprovar = useAprovarRoteiro()
  const rejeitar = useRejeitarRoteiro()

  const handleAprovar = (videoId: string) => {
    if (confirm(`Aprovar roteiro ${videoId}?`)) {
      aprovar.mutate(videoId)
    }
  }

  const handleRejeitar = (videoId: string) => {
    if (confirm(`Rejeitar roteiro ${videoId}?`)) {
      rejeitar.mutate(videoId)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Revisão Manual</h1>
        <p className="text-muted-foreground">Roteiros pendentes de aprovação</p>
      </div>

      {isLoading ? (
        <p>Carregando...</p>
      ) : pendentes && pendentes.length > 0 ? (
        <div className="grid gap-4">
          {pendentes.map((roteiro) => (
            <div key={roteiro.video_id} className="bg-card border border-border rounded-lg p-6">
              <div className="flex justify-between items-start">
                <div className="space-y-2 flex-1">
                  <div className="flex items-center gap-4">
                    <span className="text-xs text-muted-foreground font-mono">{roteiro.video_id}</span>
                    <span className="px-2 py-1 rounded bg-secondary text-secondary-foreground text-xs">
                      {roteiro.nicho}
                    </span>
                  </div>
                  <h3 className="font-medium text-lg">{roteiro.titulo_sugerido}</h3>
                  <p className="text-sm text-muted-foreground">
                    Criado em: {new Date(roteiro.criado_em).toLocaleString('pt-BR')}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => handleAprovar(roteiro.video_id)}
                    disabled={aprovar.isPending}
                    className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50"
                  >
                    Aprovar
                  </button>
                  <button
                    onClick={() => handleRejeitar(roteiro.video_id)}
                    disabled={rejeitar.isPending}
                    className="px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:opacity-50"
                  >
                    Rejeitar
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-muted-foreground">Nenhum roteiro pendente de revisão</p>
        </div>
      )}
    </div>
  )
}
