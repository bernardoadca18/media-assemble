/**
 * Composição vertical para Shorts (9:16, 1080x1920).
 * Subfase 8.5 — Suporte a Shorts.
 *
 * Reaproveita componentes Vox e KenBurns com enquadramento vertical
 * e legendas em fonte maior.
 */
import React from "react";
import {
  AbsoluteFill,
  Sequence,
  useVideoConfig,
  Audio,
  staticFile,
  interpolate,
  useCurrentFrame,
} from "remotion";
import { RoteiroData, Cena } from "../Root";
import { SceneRenderer } from "./SceneRenderer";
import { SubtitlesOverlay } from "./SubtitlesOverlay";

interface VideoCompositionShortProps extends RoteiroData {}

/**
 * Componente de legenda adaptado para Shorts (fonte maior, posicionamento inferior).
 */
const SubtitlesShort: React.FC<{
  palavras: Cena["palavras_transcritas"];
  showSubtitle: boolean;
}> = ({ palavras, showSubtitle }) => {
  if (!palavras || !showSubtitle) return null;

  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const currentWordIndex = palavras.findIndex((palavra) => {
    const startFrame = Math.floor(palavra.start * fps);
    const endFrame = Math.floor(palavra.end * fps);
    return frame >= startFrame && frame <= endFrame;
  });

  if (currentWordIndex === -1) return null;

  // Agrupar palavras em frases (máximo 5 palavras por linha)
  const wordsPerLine = 4;
  const startIndex = Math.floor(currentWordIndex / wordsPerLine) * wordsPerLine;
  const endIndex = Math.min(startIndex + wordsPerLine, palavras.length);
  const currentWords = palavras.slice(startIndex, endIndex);

  const text = currentWords.map((w) => w.text).join(" ");

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: "120px",
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          padding: "16px 32px",
          borderRadius: "12px",
          maxWidth: "90%",
        }}
      >
        <p
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: 56, // Fonte maior para Shorts
            fontWeight: "bold",
            color: "white",
            margin: 0,
            textAlign: "center",
            textShadow: "2px 2px 4px rgba(0, 0, 0, 0.8)",
            lineHeight: 1.3,
          }}
        >
          {text}
        </p>
      </div>
    </AbsoluteFill>
  );
};

/**
 * Renderiza vídeo completo em formato vertical (Short).
 */
export const VideoCompositionShort: React.FC<VideoCompositionShortProps> = ({
  metadata,
  cenas,
}) => {
  const { fps } = useVideoConfig();
  const frame = useCurrentFrame();

  // Calcular frames por cena
  let currentFrame = 0;
  const sceneFrames: { cena: Cena; startFrame: number; durationInFrames: number }[] = [];

  for (const cena of cenas) {
    const durationInFrames = Math.ceil(cena.duracao_estimada_segundos * fps);
    sceneFrames.push({
      cena,
      startFrame: currentFrame,
      durationInFrames,
    });
    currentFrame += durationInFrames;
  }

  // Trilha de fundo
  let audioPath = null;
  if (metadata.audio_final_path) {
    audioPath = metadata.audio_final_path;
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* Cenas */}
      {sceneFrames.map(({ cena, startFrame, durationInFrames }) => (
        <Sequence
          key={cena.cena_id}
          from={startFrame}
          durationInFrames={durationInFrames}
        >
          <AbsoluteFill>
            <SceneRenderer
              cena={cena}
              startFrame={0}
              durationInFrames={durationInFrames}
            />

            {/* Legendas adaptadas para Shorts */}
            {cena.overlays.exibir_legenda && cena.palavras_transcritas && (
              <SubtitlesShort
                palavras={cena.palavras_transcritas}
                showSubtitle={true}
              />
            )}
          </AbsoluteFill>
        </Sequence>
      ))}

      {/* Áudio de fundo */}
      {audioPath && (
        <Audio src={staticFile(audioPath)} volume={1} />
      )}
    </AbsoluteFill>
  );
};
