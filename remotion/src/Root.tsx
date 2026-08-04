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

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="VideoPrincipal"
        component={VideoComposition}
        durationInFrames={900} // Será sobrescrito pelos dados reais
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          roteiroPath: "",
        }}
      />
    </>
  );
};
