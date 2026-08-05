/**
 * Composição principal do vídeo faceless.
 * Coordena todas as cenas, áudio e elementos visuais.
 *
 * Recebe o roteiro completo DIRETAMENTE como props (é isso que o Remotion
 * CLI entrega a partir de `--props=<arquivo.json>`: o conteúdo do arquivo
 * inteiro vira o objeto de props, não um caminho para outro arquivo).
 * Não há leitura de arquivo em tempo de render — os dados já chegam
 * prontos, então não é preciso `delayRender`/`fs.readFileSync` aqui.
 */
import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { SceneRenderer } from "./SceneRenderer";
import { AudioTrack } from "./AudioTrack";
import { RoteiroData } from "../Root";

export const VideoComposition: React.FC<RoteiroData> = ({ metadata, cenas }) => {
  const fps = 30;

  // Calcular frames de início de cada cena
  let currentFrame = 0;
  const cenasComFrames = cenas.map((cena) => {
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
        narrationPath={metadata.audio_final_path}
        backgroundTrackPath={metadata.trilha_fundo}
        backgroundVolume={metadata.volume_trilha_fundo}
        duckingEnabled={true}
      />
    </AbsoluteFill>
  );
};