/**
 * Componente de comparação numérica estilo Vox.
 * Exibe valores grandes com contexto visual impactante.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill, spring } from "remotion";

interface VoxComparisonProps {
  valorPrincipal: string;
  rotuloPrincipal: string;
  valorComparacao?: string;
  rotuloComparacao?: string;
  unidade?: string;
  durationInFrames: number;
}

export const VoxComparison: React.FC<VoxComparisonProps> = ({
  valorPrincipal,
  rotuloPrincipal,
  valorComparacao,
  rotuloComparacao,
  unidade = "",
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

  const scale = interpolate(progress, [0, 1], [0.5, 1]);
  const opacity = interpolate(progress, [0, 0.3], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0A0A0A",
        justifyContent: "center",
        alignItems: "center",
        padding: "80px",
      }}
    >
      <div
        style={{
          opacity,
          transform: `scale(${scale})`,
          textAlign: "center",
        }}
      >
        {/* Valor principal */}
        <div style={{ marginBottom: valorComparacao ? "40px" : "0" }}>
          <p
            style={{
              fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
              fontSize: 120,
              fontWeight: "bold",
              color: "#FFD700",
              margin: 0,
              lineHeight: 1,
              textShadow: "0 4px 20px rgba(255, 215, 0, 0.3)",
            }}
          >
            {valorPrincipal}{unidade && <span style={{ fontSize: 60 }}>{unidade}</span>}
          </p>
          <p
            style={{
              fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
              fontSize: 36,
              color: "#FFFFFF",
              margin: "16px 0 0 0",
              opacity: 0.9,
            }}
          >
            {rotuloPrincipal}
          </p>
        </div>

        {/* Comparação opcional */}
        {valorComparacao && rotuloComparacao && (
          <div
            style={{
              marginTop: "60px",
              paddingTop: "40px",
              borderTop: "2px solid rgba(255, 255, 255, 0.2)",
            }}
          >
            <p
              style={{
                fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
                fontSize: 48,
                fontWeight: "bold",
                color: "#4FC3F7",
                margin: 0,
              }}
            >
              {valorComparacao}{unidade && <span style={{ fontSize: 32 }}>{unidade}</span>}
            </p>
            <p
              style={{
                fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
                fontSize: 24,
                color: "#FFFFFF",
                margin: "12px 0 0 0",
                opacity: 0.7,
              }}
            >
              {rotuloComparacao}
            </p>
          </div>
        )}
      </div>
    </AbsoluteFill>
  );
};
