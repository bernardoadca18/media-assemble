import { useState } from 'react'
import { useIdeiasManuais, useCriarIdeiaManual, useNichos } from '../hooks/useAPI'
import type { IdeiaManualCreate } from '../types/api'

export default function IdeiasManuais() {
  const { data: ideias, isLoading: loadingIdeias } = useIdeiasManuais()
  const { data: nichos } = useNichos()
  const criarIdeia = useCriarIdeiaManual()

  const [form, setForm] = useState<IdeiaManualCreate>({
    nicho: '',
    titulo_sugerido: '',
    descricao_breve: '',
    tendencia_relacionada: '',
    prioridade: 'normal',
  })
  const [showForm, setShowForm] = useState(false)

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!form.nicho || !form.titulo_sugerido) {
      alert('Preencha nicho e título')
      return
    }
    criarIdeia.mutate(form, {
      onSuccess: () => {
        setForm({
          nicho: '',
          titulo_sugerido: '',
          descricao_breve: '',
          tendencia_relacionada: '',
          prioridade: 'normal',
        })
        setShowForm(false)
      },
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Ideias Manuais</h1>
          <p className="text-muted-foreground">Gerencie ideias de vídeos para o pipeline</p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90"
        >
          {showForm ? 'Cancelar' : 'Nova Ideia'}
        </button>
      </div>

      {/* Create Form */}
      {showForm && (
        <form onSubmit={handleSubmit} className="bg-card border border-border rounded-lg p-6 space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium mb-1">Nicho *</label>
              <select
                value={form.nicho}
                onChange={(e) => setForm({ ...form, nicho: e.target.value })}
                className="w-full border border-border rounded-md px-3 py-2 bg-background"
                required
              >
                <option value="">Selecione...</option>
                {nichos?.map((n) => (
                  <option key={n.nome} value={n.nome}>
                    {n.nome}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium mb-1">Prioridade</label>
              <select
                value={form.prioridade}
                onChange={(e) => setForm({ ...form, prioridade: e.target.value as 'alta' | 'normal' })}
                className="w-full border border-border rounded-md px-3 py-2 bg-background"
              >
                <option value="normal">Normal</option>
                <option value="alta">Alta (substitui vaga no próximo lote)</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Título Sugerido *</label>
            <input
              type="text"
              value={form.titulo_sugerido}
              onChange={(e) => setForm({ ...form, titulo_sugerido: e.target.value })}
              className="w-full border border-border rounded-md px-3 py-2 bg-background"
              required
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Descrição Breve</label>
            <textarea
              value={form.descricao_breve || ''}
              onChange={(e) => setForm({ ...form, descricao_breve: e.target.value })}
              className="w-full border border-border rounded-md px-3 py-2 bg-background"
              rows={2}
            />
          </div>
          <div>
            <label className="block text-sm font-medium mb-1">Tendência Relacionada</label>
            <input
              type="text"
              value={form.tendencia_relacionada || ''}
              onChange={(e) => setForm({ ...form, tendencia_relacionada: e.target.value })}
              className="w-full border border-border rounded-md px-3 py-2 bg-background"
            />
          </div>
          <button
            type="submit"
            disabled={criarIdeia.isPending}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:opacity-90 disabled:opacity-50"
          >
            {criarIdeia.isPending ? 'Salvando...' : 'Salvar Ideia'}
          </button>
        </form>
      )}

      {/* List */}
      {loadingIdeias ? (
        <p>Carregando...</p>
      ) : ideias && ideias.length > 0 ? (
        <div className="bg-card border border-border rounded-lg overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left py-3 px-4 font-medium">ID</th>
                  <th className="text-left py-3 px-4 font-medium">Nicho</th>
                  <th className="text-left py-3 px-4 font-medium">Título</th>
                  <th className="text-left py-3 px-4 font-medium">Prioridade</th>
                  <th className="text-left py-3 px-4 font-medium">Status</th>
                  <th className="text-left py-3 px-4 font-medium">Criado</th>
                </tr>
              </thead>
              <tbody>
                {ideias.map((ideia) => (
                  <tr key={ideia.id} className="border-b border-border hover:bg-muted/30">
                    <td className="py-3 px-4 font-mono text-xs">{ideia.id}</td>
                    <td className="py-3 px-4">{ideia.nicho}</td>
                    <td className="py-3 px-4 max-w-xs truncate">{ideia.titulo_sugerido}</td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-1 rounded text-xs ${
                          ideia.prioridade === 'alta'
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}
                      >
                        {ideia.prioridade}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={ideia.status} />
                    </td>
                    <td className="py-3 px-4 text-muted-foreground text-xs">
                      {new Date(ideia.criado_em).toLocaleString('pt-BR')}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-muted-foreground">Nenhuma ideia cadastrada</p>
        </div>
      )}
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    pendente: 'bg-yellow-100 text-yellow-700',
    usada: 'bg-green-100 text-green-700',
    descartada: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-1 rounded text-xs ${styles[status] || 'bg-gray-100 text-gray-700'}`}>
      {status}
    </span>
  )
}
