/**
 * Efeito Ken Burns para imagens estáticas.
 * Aplica zoom in/out ou pan lateral suave usando interpolate.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill, Img, spring, staticFile } from "remotion";

type AnimacaoTipo = "ken_burns_zoom_in" | "ken_burns_zoom_out" | "pan_lateral";

interface KenBurnsImageProps {
  src: string;
  animacao: AnimacaoTipo;
  durationInFrames: number;
}

export const KenBurnsImage: React.FC<KenBurnsImageProps> = ({
  src,
  animacao,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Animação suave com spring physics
  const progress = spring({
    frame,
    fps,
    config: {
      damping: 100,
      stiffness: 200,
      mass: 0.5,
    },
  });

  // Calcular transformações baseado no tipo de animação
  let scale = 1;
  let translateX = 0;
  let translateY = 0;

  switch (animacao) {
    case "ken_burns_zoom_in":
      scale = interpolate(progress, [0, 1], [1, 1.3]);
      break;
    case "ken_burns_zoom_out":
      scale = interpolate(progress, [0, 1], [1.3, 1]);
      break;
    case "pan_lateral":
      translateX = interpolate(progress, [0, 1], [-50, 50]);
      scale = 1.15; // Zoom leve para evitar bordas
      break;
  }

  return (
    <AbsoluteFill style={{ overflow: "hidden" }}>
      <Img
        src={staticFile(src)}
        style={{
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${scale}) translate(${translateX}px, ${translateY}px)`,
        }}
      />
    </AbsoluteFill>
  );
};
