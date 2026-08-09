import { useState } from 'react'
import { useExecucoes, useRetomarExecucao } from '../hooks/useAPI'
import type { ExecucaoResumo } from '../types/api'

export default function Execucoes() {
  const [statusFilter, setStatusFilter] = useState<string>('')
  const { data: execucoes, isLoading } = useExecucoes({ status: statusFilter || undefined, limite: 200 })
  const retomar = useRetomarExecucao()

  const handleRetomar = (videoId: string) => {
    if (confirm(`Retomar execução ${videoId}?`)) {
      retomar.mutate(videoId)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Execuções</h1>
        <p className="text-muted-foreground">Histórico de execuções do pipeline</p>
      </div>

      {/* Filters */}
      <div className="flex gap-4">
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="border border-border rounded-md px-3 py-2 bg-background"
        >
          <option value="">Todos os status</option>
          <option value="sucesso">Sucesso</option>
          <option value="falha">Falha</option>
        </select>
      </div>

      {/* Table */}
      {isLoading ? (
        <p>Carregando...</p>
      ) : (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left py-3 px-4 font-medium">Video ID</th>
                  <th className="text-left py-3 px-4 font-medium">Nicho</th>
                  <th className="text-left py-3 px-4 font-medium">Etapa</th>
                  <th className="text-left py-3 px-4 font-medium">Status</th>
                  <th className="text-left py-3 px-4 font-medium">Motivo Falha</th>
                  <th className="text-left py-3 px-4 font-medium">Criado</th>
                  <th className="text-left py-3 px-4 font-medium">Ações</th>
                </tr>
              </thead>
              <tbody>
                {execucoes?.map((exec) => (
                  <ExecucaoRow key={exec.video_id} exec={exec} onRetomar={handleRetomar} />
                ))}
              </tbody>
            </table>
          </div>
          {execucoes?.length === 0 && (
            <p className="text-center text-muted-foreground py-8">Nenhuma execução encontrada</p>
          )}
        </div>
      )}
    </div>
  )
}

function ExecucaoRow({
  exec,
  onRetomar,
}: {
  exec: ExecucaoResumo
  onRetomar: (videoId: string) => void
}) {
  return (
    <tr className="border-b border-border hover:bg-muted/30">
      <td className="py-3 px-4 font-mono text-xs">{exec.video_id}</td>
      <td className="py-3 px-4">{exec.nicho}</td>
      <td className="py-3 px-4">{exec.etapa_atual}</td>
      <td className="py-3 px-4">
        <StatusBadge sucesso={exec.sucesso} />
      </td>
      <td className="py-3 px-4 text-red-600 text-xs max-w-xs truncate">{exec.motivo_falha || '-'}</td>
      <td className="py-3 px-4 text-muted-foreground text-xs">
        {new Date(exec.criado_em).toLocaleString('pt-BR')}
      </td>
      <td className="py-3 px-4">
        {exec.sucesso === false && (
          <button
            onClick={() => onRetomar(exec.video_id)}
            className="text-xs bg-primary text-primary-foreground px-2 py-1 rounded hover:opacity-90"
          >
            Retomar
          </button>
        )}
      </td>
    </tr>
  )
}

function StatusBadge({ sucesso }: { sucesso: boolean | null }) {
  if (sucesso === null) {
    return <span className="px-2 py-1 rounded bg-gray-100 text-gray-700 text-xs">Em andamento</span>
  }
  if (sucesso) {
    return <span className="px-2 py-1 rounded bg-green-100 text-green-700 text-xs">Sucesso</span>
  }
  return <span className="px-2 py-1 rounded bg-red-100 text-red-700 text-xs">Falha</span>
}
