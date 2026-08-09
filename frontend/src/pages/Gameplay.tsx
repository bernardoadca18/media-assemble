import { useState } from 'react'
import { useSegmentosGameplay, useEstatisticasGameplay } from '../hooks/useAPI'

export default function Gameplay() {
  const [jogoFilter, setJogoFilter] = useState<string>('')
  const [intensidadeFilter, setIntensidadeFilter] = useState<string>('')

  const { data: segmentos, isLoading: loadingSegmentos } = useSegmentosGameplay({
    jogo: jogoFilter || undefined,
    intensidade: intensidadeFilter || undefined,
    limite: 100,
  })
  const { data: estatisticas } = useEstatisticasGameplay()

  // Extract unique jogos from estatisticas
  const jogos = estatisticas?.map((e) => e.jogo) ?? []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Gameplay</h1>
        <p className="text-muted-foreground">Segmentos de gameplay indexados</p>
      </div>

      {/* Estatísticas por Jogo */}
      {estatisticas && estatisticas.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {estatisticas.map((stat) => (
            <div key={stat.jogo} className="bg-card border border-border rounded-lg p-6">
              <h3 className="font-semibold text-lg">{stat.jogo}</h3>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Total segmentos:</span>
                  <span className="font-medium">{stat.total_segmentos}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Duração total:</span>
                  <span className="font-medium">{stat.duracao_total_formatada}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Taxa aprovação:</span>
                  <span className="font-medium">{stat.taxa_aprovacao.toFixed(1)}%</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filtros */}
      <div className="flex gap-4">
        <select
          value={jogoFilter}
          onChange={(e) => setJogoFilter(e.target.value)}
          className="border border-border rounded-md px-3 py-2 bg-background"
        >
          <option value="">Todos os jogos</option>
          {jogos.map((jogo) => (
            <option key={jogo} value={jogo}>
              {jogo}
            </option>
          ))}
        </select>
        <select
          value={intensidadeFilter}
          onChange={(e) => setIntensidadeFilter(e.target.value)}
          className="border border-border rounded-md px-3 py-2 bg-background"
        >
          <option value="">Todas as intensidades</option>
          <option value="calmo">Calmo</option>
          <option value="moderado">Moderado</option>
          <option value="intenso">Intenso</option>
        </select>
      </div>

      {/* Tabela de Segmentos */}
      {loadingSegmentos ? (
        <p>Carregando...</p>
      ) : segmentos && segmentos.length > 0 ? (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left py-3 px-4 font-medium">ID</th>
                  <th className="text-left py-3 px-4 font-medium">Jogo</th>
                  <th className="text-left py-3 px-4 font-medium">Duração</th>
                  <th className="text-left py-3 px-4 font-medium">Score</th>
                  <th className="text-left py-3 px-4 font-medium">Intensidade</th>
                  <th className="text-left py-3 px-4 font-medium">Usado em</th>
                  <th className="text-left py-3 px-4 font-medium">Criado</th>
                </tr>
              </thead>
              <tbody>
                {segmentos.map((seg) => (
                  <tr key={seg.id} className="border-b border-border hover:bg-muted/30">
                    <td className="py-3 px-4 font-mono text-xs">{seg.id}</td>
                    <td className="py-3 px-4">{seg.jogo_origem}</td>
                    <td className="py-3 px-4">{seg.duracao_segundos.toFixed(1)}s</td>
                    <td className="py-3 px-4">{seg.score_movimento.toFixed(2)}</td>
                    <td className="py-3 px-4">
                      <IntensidadeBadge intensidade={seg.faixa_intensidade} />
                    </td>
                    <td className="py-3 px-4 text-xs text-muted-foreground">
                      {seg.usado_em.length > 0 ? `${seg.usado_em.length} vídeos` : 'Não usado'}
                    </td>
                    <td className="py-3 px-4 text-xs text-muted-foreground">
                      {new Date(seg.criado_em).toLocaleDateString('pt-BR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-muted-foreground">Nenhum segmento encontrado</p>
        </div>
      )}
    </div>
  )
}

function IntensidadeBadge({ intensidade }: { intensidade: string }) {
  const styles: Record<string, string> = {
    calmo: 'bg-blue-100 text-blue-700',
    moderado: 'bg-yellow-100 text-yellow-700',
    intenso: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-1 rounded text-xs ${styles[intensidade] || 'bg-gray-100 text-gray-700'}`}>
      {intensidade}
    </span>
  )
}
