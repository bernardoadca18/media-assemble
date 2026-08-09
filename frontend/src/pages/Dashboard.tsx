import { useGPUStatus, useExecucoes, usePendentesRevisao } from '../hooks/useAPI'

export default function Dashboard() {
  const { data: gpuStatus } = useGPUStatus()
  const { data: execucoes } = useExecucoes({ limite: 100 })
  const { data: pendentesRevisao } = usePendentesRevisao()

  // Calculate stats
  const stats = {
    total: execucoes?.length ?? 0,
    sucesso: execucoes?.filter((e) => e.sucesso === true).length ?? 0,
    falha: execucoes?.filter((e) => e.sucesso === false).length ?? 0,
    pendentes: pendentesRevisao?.length ?? 0,
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Visão geral do pipeline</p>
      </div>

      {/* GPU Status Card */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold">GPU Status</h2>
            <p className="text-sm text-muted-foreground">
              {gpuStatus?.mensagem ?? 'Carregando...'}
            </p>
          </div>
          <div
            className={`w-4 h-4 rounded-full ${
              gpuStatus?.disponivel ? 'bg-green-500' : 'bg-red-500'
            }`}
          />
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard title="Total Execuções" value={stats.total} />
        <StatCard title="Sucesso" value={stats.sucesso} variant="success" />
        <StatCard title="Falhas" value={stats.falha} variant="danger" />
        <StatCard title="Pendentes Revisão" value={stats.pendentes} variant="warning" />
      </div>

      {/* Recent Execuções */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Execuções Recentes</h2>
        {execucoes && execucoes.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-2 px-3">Video ID</th>
                  <th className="text-left py-2 px-3">Nicho</th>
                  <th className="text-left py-2 px-3">Etapa</th>
                  <th className="text-left py-2 px-3">Status</th>
                  <th className="text-left py-2 px-3">Criado</th>
                </tr>
              </thead>
              <tbody>
                {execucoes.slice(0, 10).map((exec) => (
                  <tr key={exec.video_id} className="border-b border-border">
                    <td className="py-2 px-3 font-mono text-xs">{exec.video_id}</td>
                    <td className="py-2 px-3">{exec.nicho}</td>
                    <td className="py-2 px-3">{exec.etapa_atual}</td>
                    <td className="py-2 px-3">
                      <StatusBadge sucesso={exec.sucesso} />
                    </td>
                    <td className="py-2 px-3 text-muted-foreground">
                      {new Date(exec.criado_em).toLocaleDateString('pt-BR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-muted-foreground">Nenhuma execução encontrada</p>
        )}
      </div>
    </div>
  )
}

function StatCard({
  title,
  value,
  variant = 'default',
}: {
  title: string
  value: number
  variant?: 'default' | 'success' | 'danger' | 'warning'
}) {
  const colors = {
    default: 'text-foreground',
    success: 'text-green-600',
    danger: 'text-red-600',
    warning: 'text-yellow-600',
  }

  return (
    <div className="bg-card border border-border rounded-lg p-6">
      <p className="text-sm text-muted-foreground">{title}</p>
      <p className={`text-3xl font-bold ${colors[variant]}`}>{value}</p>
    </div>
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
