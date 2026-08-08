/**
 * Renderiza uma cena individual com imagem/vídeo e overlays.
 * Despacha para componente correto baseado em estilo_visual.
 */
import React from "react";
import { AbsoluteFill, useVideoConfig, Video, Sequence, staticFile } from "remotion";
import { KenBurnsImage } from "./KenBurnsImage";
import { SubtitlesOverlay } from "./SubtitlesOverlay";
import { VoxComparison } from "./VoxComparison";
import { VoxTimeline } from "./VoxTimeline";
import { VoxCallout } from "./VoxCallout";
import { VoxTextReveal } from "./VoxTextReveal";
import { Cena, Palavra, ComparacaoNumerica, LinhaDoTempo, Citacao, GraficoComparativo } from "../Root";

interface SceneRendererProps {
  cena: Cena;
  startFrame: number;
  durationInFrames: number;
}

/**
 * Renderiza elemento gráfico do estilo vox_motion.
 */
const renderElementoGrafico = (
  elementoGrafico: ComparacaoNumerica | LinhaDoTempo | Citacao | GraficoComparativo | null | undefined,
  durationInFrames: number
): React.ReactElement | null => {
  if (!elementoGrafico) return null;

  if ("valor_principal" in elementoGrafico) {
    // ComparacaoNumerica
    return (
      <VoxComparison
        valorPrincipal={elementoGrafico.valor_principal}
        rotuloPrincipal={elementoGrafico.rotulo_principal}
        valorComparacao={elementoGrafico.valor_comparacao}
        rotuloComparacao={elementoGrafico.rotulo_comparacao}
        unidade={elementoGrafico.unidade}
        durationInFrames={durationInFrames}
      />
    );
  }

  if ("eventos" in elementoGrafico) {
    // LinhaDoTempo
    return (
      <VoxTimeline
        eventos={elementoGrafico.eventos}
        anoInicio={elementoGrafico.ano_inicio}
        anoFim={elementoGrafico.ano_fim}
        titulo={elementoGrafico.titulo}
        durationInFrames={durationInFrames}
      />
    );
  }

  if ("autor" in elementoGrafico) {
    // Citacao
    return (
      <VoxCallout
        texto={elementoGrafico.texto}
        autor={elementoGrafico.autor}
        contexto={elementoGrafico.contexto}
        durationInFrames={durationInFrames}
      />
    );
  }

  if ("itens" in elementoGrafico && "valores" in elementoGrafico) {
    // GraficoComparativo - renderizar como VoxComparison simplificado
    const maiorValor = elementoGrafico.valores[0];
    const rotuloMaior = elementoGrafico.itens[0];
    return (
      <VoxComparison
        valorPrincipal={maiorValor}
        rotuloPrincipal={rotuloMaior}
        unidade={elementoGrafico.unidade}
        durationInFrames={durationInFrames}
      />
    );
  }

  return null;
};

export const SceneRenderer: React.FC<SceneRendererProps> = ({
  cena,
  startFrame,
  durationInFrames,
}) => {
  const { fps } = useVideoConfig();

  // Estilo visual: ken_burns (default) ou vox_motion
  const estiloVisual = cena.estilo_visual || "ken_burns";

  // Para vox_motion, não precisa de asset_resolvido_path
  if (estiloVisual === "ken_burns" && !cena.asset_resolvido_path) {
    return null;
  }

  const isVideo = cena.midia.tipo_asset_preferencial === "video";

  return (
    <Sequence from={startFrame} durationInFrames={durationInFrames}>
      <AbsoluteFill>
        {/* Renderizar baseado no estilo visual */}
        {estiloVisual === "vox_motion" ? (
          // Estilo Vox Motion Graphics
          renderElementoGrafico(cena.elemento_grafico, durationInFrames)
        ) : (
          // Estilo Ken Burns (default)
          <>
            {/* Asset visual (imagem ou vídeo) */}
            {isVideo ? (
              <Video
                src={staticFile(cena.asset_resolvido_path!)}
                style={{
                  width: "100%",
                  height: "100%",
                  objectFit: "cover",
                }}
                muted
              />
            ) : (
              <KenBurnsImage
                src={cena.asset_resolvido_path!}
                animacao={cena.efeitos_visuais.animacao_imagem}
                durationInFrames={durationInFrames}
              />
            )}
          </>
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
