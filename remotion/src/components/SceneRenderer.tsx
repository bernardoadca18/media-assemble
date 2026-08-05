/**
 * Renderiza uma cena individual com imagem/vídeo e overlays.
 */
import React from "react";
import { AbsoluteFill, useVideoConfig, Video, Sequence, staticFile } from "remotion";
import { KenBurnsImage } from "./KenBurnsImage";
import { SubtitlesOverlay } from "./SubtitlesOverlay";
import { Cena, Palavra } from "../Root";

interface SceneRendererProps {
  cena: Cena;
  startFrame: number;
  durationInFrames: number;
}

export const SceneRenderer: React.FC<SceneRendererProps> = ({
  cena,
  startFrame,
  durationInFrames,
}) => {
  const { fps } = useVideoConfig();

  // Verificar se tem asset resolvido
  if (!cena.asset_resolvido_path) {
    return null;
  }

  const isVideo = cena.midia.tipo_asset_preferencial === "video";

  return (
    <Sequence from={startFrame} durationInFrames={durationInFrames}>
      <AbsoluteFill>
        {/* Asset visual (imagem ou vídeo) */}
        {isVideo ? (
          <Video
            src={staticFile(cena.asset_resolvido_path)}
            style={{
              width: "100%",
              height: "100%",
              objectFit: "cover",
            }}
            muted
          />
        ) : (
          <KenBurnsImage
            src={cena.asset_resolvido_path}
            animacao={cena.efeitos_visuais.animacao_imagem}
            durationInFrames={durationInFrames}
          />
        )}

        {/* Legendas */}
        {cena.overlays.exibir_legenda && cena.palavras_transcritas && (
          <SubtitlesOverlay
            palavras={cena.palavras_transcritas}
            showSubtitle={true}
          />
        )}

        {/* Texto de destaque (se houver) */}
        {cena.overlays.texto_destaque_tela && (
          <AbsoluteFill
            style={{
              justifyContent: "center",
              alignItems: "center",
            }}
          >
            <div
              style={{
                backgroundColor: "rgba(0, 0, 0, 0.6)",
                padding: "24px 48px",
                borderRadius: "16px",
                maxWidth: "70%",
              }}
            >
              <p
                style={{
                  fontFamily: "Arial, sans-serif",
                  fontSize: "64px",
                  fontWeight: "bold",
                  color: "white",
                  margin: 0,
                  textAlign: "center",
                  textTransform: "uppercase",
                  letterSpacing: "2px",
                }}
              >
                {cena.overlays.texto_destaque_tela}
              </p>
            </div>
          </AbsoluteFill>
        )}
      </AbsoluteFill>
    </Sequence>
  );
};
