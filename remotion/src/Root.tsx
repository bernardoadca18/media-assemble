import React from "react";
import { Composition } from "remotion";
import { VideoComposition } from "./components/VideoComposition";

// Tipo para os dados do roteiro serializado do Python
export interface RoteiroData {
  metadata: {
    video_id: string;
    nicho: string;
    titulo_sugerido: string;
    duracao_estimada_segundos: number;
    trilha_fundo: string;
    volume_trilha_fundo: number;
    audio_final_path: string | null;
    palavras_transcritas: Palavra[] | null;
    video_final_path: string | null;
  };
  cenas: Cena[];
}

export interface Cena {
  cena_id: number;
  ordem: number;
  texto_locucao: string;
  duracao_estimada_segundos: number;
  midia: Midia;
  efeitos_visuais: EfeitosVisuais;
  overlays: Overlays;
  audio_path: string | null;
  palavras_transcritas: Palavra[] | null;
  wer_final: number | null;
  revisao_manual_necessaria: boolean;
  asset_resolvido_path: string | null;
  asset_origem: string | null;
}

export interface Midia {
  tipo_asset_preferencial: "imagem" | "video";
  keywords_busca: string[];
  fallback_query: string;
  duracao_minima: number;
}

export interface EfeitosVisuais {
  animacao_imagem: "ken_burns_zoom_in" | "ken_burns_zoom_out" | "pan_lateral";
  transicao_saida: string;
  duracao_transicao_segundos: number;
}

export interface Overlays {
  exibir_legenda: boolean;
  texto_destaque_tela: string | null;
}

export interface Palavra {
  text: string;
  start: number;
  end: number;
}

const FPS = 30;

// Props default para o preview do Remotion Studio (antes de --props reais
// serem fornecidos pelo bridge Python). Um roteiro vazio e válido é
// suficiente para o Studio não quebrar ao listar a composição.
const roteiroPadrao: RoteiroData = {
  metadata: {
    video_id: "preview",
    nicho: "",
    titulo_sugerido: "",
    duracao_estimada_segundos: 10,
    trilha_fundo: "",
    volume_trilha_fundo: 0.15,
    audio_final_path: null,
    palavras_transcritas: null,
    video_final_path: null,
  },
  cenas: [],
};

/**
 * Calcula a duração total do vídeo (em frames) a partir da soma real das
 * durações das cenas do roteiro recebido via --props.
 *
 * IMPORTANTE: sem isso, a Composition usaria sempre o `durationInFrames`
 * estático declarado abaixo (fallback do Studio), cortando ou esticando
 * todo vídeo real para essa duração fixa, independentemente da duração
 * verdadeira do roteiro.
 */
function calcularDuracaoTotalFrames(roteiro: RoteiroData): number {
  const totalFrames = roteiro.cenas.reduce(
    (acc, cena) => acc + Math.ceil(cena.duracao_estimada_segundos * FPS),
    0
  );
  // Nunca retorna 0 (Remotion exige durationInFrames >= 1)
  return Math.max(totalFrames, 1);
}

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoPrincipal"
        component={VideoComposition}
        durationInFrames={300} // Fallback para o Studio antes de props reais; sobrescrito por calculateMetadata em render real
        fps={FPS}
        width={1920}
        height={1080}
        defaultProps={roteiroPadrao}
        calculateMetadata={({ props }) => {
          return {
            durationInFrames: calcularDuracaoTotalFrames(props as RoteiroData),
          };
        }}
      />
    </>
  );
};