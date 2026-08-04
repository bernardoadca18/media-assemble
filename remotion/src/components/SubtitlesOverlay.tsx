/**
 * Overlay de legendas palavra-a-palavra.
 * Mostra as palavras sincronizadas com o timestamp do áudio.
 */
import React from "react";
import { useCurrentFrame, useVideoConfig, AbsoluteFill, interpolate } from "remotion";
import { Palavra } from "../Root";

interface SubtitlesOverlayProps {
  palavras: Palavra[];
  showSubtitle: boolean;
}

export const SubtitlesOverlay: React.FC<SubtitlesOverlayProps> = ({
  palavras,
  showSubtitle,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  if (!showSubtitle || !palavras || palavras.length === 0) {
    return null;
  }

  // Converter frame para segundos
  const currentTime = frame / fps;

  // Encontrar a palavra atual (sendo falada no momento)
  const palavraAtual = palavras.find(
    (p) => currentTime >= p.start && currentTime < p.end
  );

  // Encontrar palavras recentemente faladas (janela de contexto)
  const palavrasVisiveis = palavras
    .filter((p) => {
      // Mostrar palavra atual e as 3 anteriores
      const indiceAtual = palavras.indexOf(palavraAtual!);
      const indicePalavra = palavras.indexOf(p);
      return indicePalavra >= indiceAtual - 3 && indicePalavra <= indiceAtual;
    })
    .map((p, index, arr) => {
      const isPalavraAtual = p === palavraAtual;
      const opacity = isPalavraAtual ? 1 : interpolate(index, [0, arr.length - 1], [0.3, 0.7]);

      return {
        ...p,
        opacity,
        isPalavraAtual,
      };
    });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: "10%",
      }}
    >
      <div
        style={{
          backgroundColor: "rgba(0, 0, 0, 0.75)",
          padding: "16px 32px",
          borderRadius: "12px",
          maxWidth: "80%",
        }}
      >
        <p
          style={{
            fontFamily: "Arial, sans-serif",
            fontSize: "48px",
            color: "white",
            margin: 0,
            textAlign: "center",
            textShadow: "2px 2px 4px rgba(0, 0, 0, 0.5)",
          }}
        >
          {palavrasVisiveis.map((p, i) => (
            <span
              key={i}
              style={{
                opacity: p.opacity,
                fontWeight: p.isPalavraAtual ? "bold" : "normal",
              }}
            >
              {p.text}{" "}
            </span>
          ))}
        </p>
      </div>
    </AbsoluteFill>
  );
};
