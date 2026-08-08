/**
 * Componente de linha do tempo estilo Vox.
 * Exibe eventos sequenciais com animação visual.
 */
import React from "react";
import { interpolate, useCurrentFrame, useVideoConfig, AbsoluteFill, spring } from "remotion";

interface VoxTimelineProps {
  eventos: string[];
  anoInicio?: string;
  anoFim?: string;
  titulo?: string;
  durationInFrames: number;
}

export const VoxTimeline: React.FC<VoxTimelineProps> = ({
  eventos,
  anoInicio,
  anoFim,
  titulo,
  durationInFrames,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  // Calcular qual evento deve aparecer
  const eventoIndex = Math.min(
    Math.floor(interpolate(frame, [0, durationInFrames], [0, eventos.length], {
      extrapolateRight: "clamp",
    })),
    eventos.length - 1
  );

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "#0F0F0F",
        padding: "80px",
      }}
    >
      {/* Título */}
      {titulo && (
        <div style={{ marginBottom: "60px", textAlign: "center" }}>
          <p
            style={{
              fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
              fontSize: 48,
              fontWeight: "bold",
              color: "#FFFFFF",
              margin: 0,
            }}
          >
            {titulo}
          </p>
          {anoInicio && anoFim && (
            <p
              style={{
                fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
                fontSize: 24,
                color: "#9E9E9E",
                margin: "12px 0 0 0",
              }}
            >
              {anoInicio} — {anoFim}
            </p>
          )}
        </div>
      )}

      {/* Linha vertical */}
      <div
        style={{
          position: "absolute",
          left: "50%",
          top: "200px",
          width: "4px",
          height: "calc(100% - 300px)",
          backgroundColor: "rgba(255, 255, 255, 0.2)",
          transform: "translateX(-50%)",
        }}
      />

      {/* Eventos */}
      <div
        style={{
          position: "absolute",
          width: "100%",
          top: "220px",
        }}
      >
        {eventos.map((evento, index) => {
          const isActive = index === eventoIndex;
          const progress = spring({
            frame: frame - index * Math.floor(durationInFrames / eventos.length),
            fps,
            config: {
              damping: 100,
              stiffness: 200,
              mass: 0.5,
            },
          });

          const opacity = index <= eventoIndex ? interpolate(progress, [0, 1], [0, 1]) : 0;
          const translateX = index % 2 === 0 ? interpolate(progress, [0, 1], [-50, 0]) : interpolate(progress, [0, 1], [50, 0]);

          return (
            <div
              key={index}
              style={{
                position: "absolute",
                left: index % 2 === 0 ? "25%" : "75%",
                transform: `translateX(-50%) translateX(${translateX}px)`,
                opacity,
                marginBottom: "40px",
                textAlign: index % 2 === 0 ? "right" : "left",
              }}
            >
              <div
                style={{
                  backgroundColor: isActive ? "#FFD700" : "rgba(255, 255, 255, 0.1)",
                  padding: "20px 30px",
                  borderRadius: "8px",
                  display: "inline-block",
                }}
              >
                <p
                  style={{
                    fontFamily: "'Inter', 'Helvetica Neue', Arial, sans-serif",
                    fontSize: 28,
                    fontWeight: isActive ? "bold" : "normal",
                    color: isActive ? "#000000" : "#FFFFFF",
                    margin: 0,
                  }}
                >
                  {evento}
                </p>
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
