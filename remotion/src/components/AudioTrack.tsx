/**
 * Gerenciador de áudio com narração e trilha de fundo.
 * Aplica ducking automático na trilha durante a narração.
 */
import React from "react";
import { Audio, useCurrentFrame, useVideoConfig } from "remotion";

interface AudioTrackProps {
  narrationPath: string | null;
  backgroundTrackPath: string;
  backgroundVolume: number;
  duckingEnabled?: boolean;
}

export const AudioTrack: React.FC<AudioTrackProps> = ({
  narrationPath,
  backgroundTrackPath,
  backgroundVolume,
  duckingEnabled = true,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Volume da trilha de fundo com ducking
  // Se tiver narração, reduz o volume da trilha
  const duckingFactor = narrationPath && duckingEnabled ? 0.3 : 1;
  const adjustedBackgroundVolume = backgroundVolume * duckingFactor;

  return (
    <>
      {/* Narração principal */}
      {narrationPath && (
        <Audio
          src={narrationPath}
          volume={1}
        />
      )}

      {/* Trilha de fundo */}
      {backgroundTrackPath && (
        <Audio
          src={backgroundTrackPath}
          volume={adjustedBackgroundVolume}
          loop
        />
      )}
    </>
  );
};
