import { useState } from 'react'
import { useNichos, useCriarNicho, useAtualizarNicho, useDeletarNicho } from '../hooks/useAPI'
import type { NichoConfig, NichoCreate, NichoUpdate } from '../types/api'

export default function Nichos() {
  const { data: nichos, isLoading } = useNichos()
  const criarNicho = useCriarNicho()
  const atualizarNicho = useAtualizarNicho()
  const deletarNicho = useDeletarNicho()

  const [showForm, setShowForm] = useState(false)
  const [editingNicho, setEditingNicho] = useState<NichoConfig | null>(null)
  const [formData, setFormData] = useState<NichoCreate>({
    nome: '',
    prompt_ideacao: '',
    prompt_roteiro_adicional: '',
    prompt_roteiro_short: '',
    categoria_google_trends: 22,
    subreddits_sugeridos: [],
    gameplay_intensidade_preferida: 'moderado',
    timbre_pitch_shift: null,
    timbre_velocidade: null,
  })
  const [subredditInput, setSubredditInput] = useState('')

  const resetForm = () => {
    setFormData({
      nome: '',
      prompt_ideacao: '',
      prompt_roteiro_adicional: '',
      prompt_roteiro_short: '',
      categoria_google_trends: 22,
      subreddits_sugeridos: [],
      gameplay_intensidade_preferida: 'moderado',
      timbre_pitch_shift: null,
      timbre_velocidade: null,
    })
    setSubredditInput('')
    setEditingNicho(null)
    setShowForm(false)
  }

  const handleEdit = (nicho: NichoConfig) => {
    setEditingNicho(nicho)
    setFormData({
      nome: nicho.nome,
      prompt_ideacao: '', // Not returned by API, would need separate endpoint
      prompt_roteiro_adicional: '',
      prompt_roteiro_short: '',
      categoria_google_trends: nicho.categoria_google_trends,
      subreddits_sugeridos: nicho.subreddits_sugeridos,
      gameplay_intensidade_preferida: nicho.gameplay_intensidade_preferida,
      timbre_pitch_shift: nicho.timbre_pitch_shift,
      timbre_velocidade: nicho.timbre_velocidade,
    })
    setShowForm(true)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      if (editingNicho) {
        const updateData: NichoUpdate = {
          categoria_google_trends: formData.categoria_google_trends,
          subreddits_sugeridos: formData.subreddits_sugeridos,
          gameplay_intensidade_preferida: formData.gameplay_intensidade_preferida,
          timbre_pitch_shift: formData.timbre_pitch_shift,
          timbre_velocidade: formData.timbre_velocidade,
        }
        await atualizarNicho.mutateAsync({ nome: editingNicho.nome, data: updateData })
      } else {
        await criarNicho.mutateAsync(formData)
      }
      resetForm()
    } catch (error) {
      console.error('Erro ao salvar nicho:', error)
    }
  }

  const handleDelete = async (nome: string) => {
    if (confirm(`Tem certeza que deseja desativar o nicho "${nome}"?`)) {
      try {
        await deletarNicho.mutateAsync(nome)
      } catch (error) {
        console.error('Erro ao deletar nicho:', error)
      }
    }
  }

  const addSubreddit = () => {
    const trimmed = subredditInput.trim()
    if (trimmed && !formData.subreddits_sugeridos.includes(trimmed)) {
      setFormData({
        ...formData,
        subreddits_sugeridos: [...formData.subreddits_sugeridos, trimmed],
      })
      setSubredditInput('')
    }
  }

  const removeSubreddit = (sub: string) => {
    setFormData({
      ...formData,
      subreddits_sugeridos: formData.subreddits_sugeridos.filter((s) => s !== sub),
    })
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">Nichos</h1>
          <p className="text-muted-foreground">Configurações de nichos e canais</p>
        </div>
        <button
          onClick={() => setShowForm(true)}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
        >
          Novo Nicho
        </button>
      </div>

      {/* Form Modal */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card border border-border rounded-lg p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-semibold mb-4">
              {editingNicho ? `Editar: ${editingNicho.nome}` : 'Novo Nicho'}
            </h2>
            <form onSubmit={handleSubmit} className="space-y-4">
              {!editingNicho && (
                <div>
                  <label className="block text-sm font-medium mb-1">Nome</label>
                  <input
                    type="text"
                    value={formData.nome}
                    onChange={(e) => setFormData({ ...formData, nome: e.target.value })}
                    className="w-full px-3 py-2 border border-border rounded-md bg-background"
                    required
                  />
                </div>
              )}

              <div>
                <label className="block text-sm font-medium mb-1">Categoria Google Trends</label>
                <input
                  type="number"
                  value={formData.categoria_google_trends}
                  onChange={(e) => setFormData({ ...formData, categoria_google_trends: parseInt(e.target.value) })}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Intensidade Gameplay</label>
                <select
                  value={formData.gameplay_intensidade_preferida}
                  onChange={(e) => setFormData({ ...formData, gameplay_intensidade_preferida: e.target.value })}
                  className="w-full px-3 py-2 border border-border rounded-md bg-background"
                >
                  <option value="calmo">Calmo</option>
                  <option value="moderado">Moderado</option>
                  <option value="intenso">Intenso</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Subreddits</label>
                <div className="flex gap-2 mb-2">
                  <input
                    type="text"
                    value={subredditInput}
                    onChange={(e) => setSubredditInput(e.target.value)}
                    placeholder="ex: r/anime"
                    className="flex-1 px-3 py-2 border border-border rounded-md bg-background"
                    onKeyPress={(e) => e.key === 'Enter' && (e.preventDefault(), addSubreddit())}
                  />
                  <button
                    type="button"
                    onClick={addSubreddit}
                    className="px-4 py-2 border border-border rounded-md hover:bg-secondary"
                  >
                    Adicionar
                  </button>
                </div>
                <div className="flex flex-wrap gap-2">
                  {formData.subreddits_sugeridos.map((sub) => (
                    <span
                      key={sub}
                      className="px-2 py-1 rounded bg-secondary text-secondary-foreground text-xs flex items-center gap-1"
                    >
                      r/{sub}
                      <button type="button" onClick={() => removeSubreddit(sub)} className="ml-1 hover:text-red-500">
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Pitch Shift (semitons)</label>
                  <input
                    type="number"
                    step="0.1"
                    value={formData.timbre_pitch_shift ?? ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        timbre_pitch_shift: e.target.value ? parseFloat(e.target.value) : null,
                      })
                    }
                    placeholder="ex: -2.0"
                    className="w-full px-3 py-2 border border-border rounded-md bg-background"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Velocidade Fala</label>
                  <input
                    type="number"
                    step="0.01"
                    min="0.8"
                    max="1.2"
                    value={formData.timbre_velocidade ?? ''}
                    onChange={(e) =>
                      setFormData({
                        ...formData,
                        timbre_velocidade: e.target.value ? parseFloat(e.target.value) : null,
                      })
                    }
                    placeholder="ex: 1.05"
                    className="w-full px-3 py-2 border border-border rounded-md bg-background"
                  />
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-4">
                <button
                  type="button"
                  onClick={resetForm}
                  className="px-4 py-2 border border-border rounded-md hover:bg-secondary"
                >
                  Cancelar
                </button>
                <button
                  type="submit"
                  disabled={criarNicho.isPending || atualizarNicho.isPending}
                  className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
                >
                  {editingNicho ? 'Salvar' : 'Criar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {isLoading ? (
        <p>Carregando...</p>
      ) : nichos && nichos.length > 0 ? (
        <div className="grid gap-6">
          {nichos.map((nicho) => (
            <div key={nicho.nome} className="bg-card border border-border rounded-lg p-6">
              <div className="flex justify-between items-start mb-4">
                <div>
                  <h2 className="text-xl font-semibold">{nicho.nome}</h2>
                  <p className="text-sm text-muted-foreground">
                    Categoria Google Trends: {nicho.categoria_google_trends}
                  </p>
                </div>
                <div className="flex gap-2">
                  {nicho.prompt_roteiro_short_configurado ? (
                    <span className="px-2 py-1 rounded bg-green-100 text-green-700 text-xs">
                      Prompt configurado
                    </span>
                  ) : (
                    <span className="px-2 py-1 rounded bg-yellow-100 text-yellow-700 text-xs">
                      Sem prompt
                    </span>
                  )}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Subreddits */}
                <div>
                  <h3 className="text-sm font-medium mb-2">Subreddits Sugeridos</h3>
                  <div className="flex flex-wrap gap-2">
                    {nicho.subreddits_sugeridos.map((sub) => (
                      <span
                        key={sub}
                        className="px-2 py-1 rounded bg-secondary text-secondary-foreground text-xs"
                      >
                        r/{sub}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Configurações */}
                <div className="space-y-3">
                  <div>
                    <h3 className="text-sm font-medium mb-2">Gameplay</h3>
                    <p className="text-sm text-muted-foreground">
                      Intensidade preferida:{' '}
                      <span className="font-medium text-foreground">
                        {nicho.gameplay_intensidade_preferida}
                      </span>
                    </p>
                  </div>

                  {(nicho.timbre_pitch_shift || nicho.timbre_velocidade) && (
                    <div>
                      <h3 className="text-sm font-medium mb-2">Timbre TTS</h3>
                      <div className="text-sm text-muted-foreground space-y-1">
                        {nicho.timbre_pitch_shift && (
                          <p>
                            Pitch shift:{' '}
                            <span className="font-medium text-foreground">
                              {nicho.timbre_pitch_shift} semitons
                            </span>
                          </p>
                        )}
                        {nicho.timbre_velocidade && (
                          <p>
                            Velocidade:{' '}
                            <span className="font-medium text-foreground">
                              {nicho.timbre_velocidade}x
                            </span>
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Actions */}
              <div className="flex justify-end gap-2 mt-4 pt-4 border-t border-border">
                <button
                  onClick={() => handleEdit(nicho)}
                  className="px-3 py-1.5 text-sm border border-border rounded hover:bg-secondary"
                >
                  Editar
                </button>
                <button
                  onClick={() => handleDelete(nicho.nome)}
                  className="px-3 py-1.5 text-sm border border-red-300 text-red-600 rounded hover:bg-red-50"
                >
                  Desativar
                </button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="bg-card border border-border rounded-lg p-8 text-center">
          <p className="text-muted-foreground">Nenhum nicho configurado</p>
        </div>
      )}
    </div>
  )
}
