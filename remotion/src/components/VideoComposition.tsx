/**
 * Composição principal do vídeo faceless.
 * Coordena todas as cenas, áudio e elementos visuais.
 */
import React from "react";
import {
  AbsoluteFill,
  useVideoConfig,
  Sequence,
  useCurrentFrame,
  continueRender,
  delayRender,
} from "remotion";
import { SceneRenderer } from "./SceneRenderer";
import { AudioTrack } from "./AudioTrack";
import { RoteiroData } from "../Root";
import * as fs from "fs";
import * as path from "path";

interface VideoCompositionProps {
  roteiroPath: string;
}

export const VideoComposition: React.FC<VideoCompositionProps> = ({
  roteiroPath,
}) => {
  const { fps, durationInFrames } = useVideoConfig();
  const frame = useCurrentFrame();
  const [roteiro, setRoteiro] = React.useState<RoteiroData | null>(null);
  const [handle] = React.useState(() => delayRender("Carregando roteiro..."));

  // Carregar dados do roteiro do arquivo JSON
  React.useEffect(() => {
    if (!roteiroPath) {
      continueRender(handle);
      return;
    }

    try {
      const roteiroJson = fs.readFileSync(roteiroPath, "utf-8");
      const data = JSON.parse(roteiroJson) as RoteiroData;
      setRoteiro(data);
      continueRender(handle);
    } catch (error) {
      console.error("Erro ao carregar roteiro:", error);
      continueRender(handle);
    }
  }, [roteiroPath, handle]);

  if (!roteiro) {
    return (
      <AbsoluteFill
        style={{
          backgroundColor: "#000",
          justifyContent: "center",
          alignItems: "center",
        }}
      >
        <p style={{ color: "white", fontSize: "48px" }}>Carregando...</p>
      </AbsoluteFill>
    );
  }

  // Calcular duração total baseado nas cenas
  const totalFrames = roteiro.cenas.reduce((acc, cena) => {
    return acc + Math.ceil(cena.duracao_estimada_segundos * fps);
  }, 0);

  // Calcular frames de início de cada cena
  let currentFrame = 0;
  const cenasComFrames = roteiro.cenas.map((cena) => {
    const frames = Math.ceil(cena.duracao_estimada_segundos * fps);
    const startFrame = currentFrame;
    currentFrame += frames;
    return {
      cena,
      startFrame,
      durationInFrames: frames,
    };
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Cenas */}
      {cenasComFrames.map(({ cena, startFrame, durationInFrames }) => (
        <SceneRenderer
          key={cena.cena_id}
          cena={cena}
          startFrame={startFrame}
          durationInFrames={durationInFrames}
        />
      ))}

      {/* Trilha de áudio */}
      <AudioTrack
        narrationPath={roteiro.metadata.audio_final_path}
        backgroundTrackPath={roteiro.metadata.trilha_fundo}
        backgroundVolume={roteiro.metadata.volume_trilha_fundo}
        duckingEnabled={true}
      />
    </AbsoluteFill>
  );
};
