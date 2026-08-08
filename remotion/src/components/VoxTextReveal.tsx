/**
 * Componente de texto cinético estilo Vox.
 * Anima texto com fade in/slide up para destaque visual.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill, spring } from "remotion";

interface VoxTextRevealProps {
  text: string;
  fontSize?: number;
  color?: string;
  backgroundColor?: string;
  durationInFrames: number;
}

export const VoxTextReveal: React.FC<VoxTextRevealProps> = ({
  text,
  fontSize = 72,
  color = "#FFFFFF",
  backgroundColor = "#1A1A1A",
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const progress = spring({
    frame,
    fps,
    config: {
      damping: 100,
      stiffness: 200,
      mass: 0.5,
    },
  });

  const opacity = interpolate(progress, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  const translateY = interpolate(progress, [0, 1], [40, 0]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor,
        justifyContent: "center",
        alignItems: "center",
        padding: "80px",
      }}
    >
      <div
        style={{
          opacity,
          transform: `translateY(${translateY}px)`,
        }}
      >
        <p
          style={{
            fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
            fontSize,
            fontWeight: "bold",
            color,
            margin: 0,
            textAlign: "center",
            lineHeight: 1.2,
            textShadow: "0 4px 12px rgba(0, 0, 0, 0.3)",
          }}
        >
          {text}
        </p>
      </div>
    </AbsoluteFill>
  );
};
