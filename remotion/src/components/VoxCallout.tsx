/**
 * Componente de callout estilo Vox.
 * Exibe citações ou destaques com animação visual.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill, spring } from "remotion";

interface VoxCalloutProps {
  texto: string;
  autor: string;
  contexto?: string;
  durationInFrames: number;
}

export const VoxCallout: React.FC<VoxCalloutProps> = ({
  texto,
  autor,
  contexto,
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

  const scale = interpolate(progress, [0, 1], [0.9, 1]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#1A1A1A",
        justifyContent: "center",
        alignItems: "center",
        padding: "100px",
      }}
    >
      {/* Aspas decorativas */}
      <div
        style={{
          position: "absolute",
          top: "80px",
          left: "120px",
          fontSize: 200,
          color: "rgba(255, 215, 0, 0.15)",
          fontFamily: "Georgia, serif",
          lineHeight: 1,
        }}
      >
        "
      </div>

      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          maxWidth: "1400px",
        }}
      >
        {/* Texto da citação */}
        <p
          style={{
            fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
            fontSize: 56,
            fontWeight: "bold",
            color: "#FFFFFF",
            margin: 0,
            lineHeight: 1.3,
            textAlign: "center",
            textShadow: "0 2px 8px rgba(0, 0, 0, 0.2)",
          }}
        >
          {texto}
        </p>

        {/* Autor */}
        <div style={{ marginTop: "48px", textAlign: "center" }}>
          <p
            style={{
              fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
              fontSize: 32,
              fontWeight: "bold",
              color: "#FFD700",
              margin: 0,
            }}
          >
            — {autor}
          </p>

          {/* Contexto opcional */}
          {contexto && (
            <p
              style={{
                fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
                fontSize: 24,
                color: "#9E9E9E",
                margin: "12px 0 0 0",
              }}
            >
              {contexto}
            </p>
          )}
        </div>
      </div>

      {/* Aspas decorativas de fechamento */}
      <div
        style={{
          position: "absolute",
          bottom: "80px",
          right: "120px",
          fontSize: 200,
          color: "rgba(255, 215, 0, 0.15)",
          fontFamily: "Georgia, serif",
          lineHeight: 1,
        }}
      >
        "
      </div>
    </AbsoluteFill>
  );
};
