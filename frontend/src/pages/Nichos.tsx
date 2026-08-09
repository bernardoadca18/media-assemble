import { useNichos } from '../hooks/useAPI'

export default function Nichos() {
  const { data: nichos, isLoading } = useNichos()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Nichos</h1>
        <p className="text-muted-foreground">Configurações de nichos e canais</p>
      </div>

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
