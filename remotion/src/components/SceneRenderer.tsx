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

/**
 * Renderiza gameplay_bg com crop vertical para Shorts.
 * Fase 9.4 — Recorte vertical para Shorts/TikTok no modo gameplay.
 *
 * Gameplay videos são 16:9 (horizontal). Para Shorts 9:16 (vertical),
 * aplicamos crop vertical centrado, com offset Y configurável por jogo.
 */
const GameplayBgRenderer: React.FC<{
  src: string;
  cropOffsetY: number;
}> = ({ src, cropOffsetY }) => {
  const { width, height } = useVideoConfig();

  // Para vídeo vertical (9:16), o gameplay horizontal (16:9) precisa ser:
  // 1. Escalado para cobrir a altura vertical
  // 2. Cropado horizontalmente para remover barras laterais
  // 3. Offset Y aplicado para ajustar enquadramento

  // O gameplay tem aspect ratio 16:9 (1920x1080)
  // O Short tem aspect ratio 9:16 (1080x1920)
  // Para cobrir a altura 1920, precisamos escalar o gameplay para:
  // width_gameplay = 1920 * (16/9) = 3413.33
  // Então cropar para 1080 de largura, centrado

  // Calculamos o scale para cobrir a altura
  const gameplayAspect = 16 / 9;
  const shortAspect = width / height;

  // Scale para cobrir a altura (fit vertical)
  const scale = height / 1080; // Escala gameplay 1080p para altura do Short

  return (
    <AbsoluteFill>
      <Video
        src={staticFile(src)}
        style={{
          position: "absolute",
          width: 1920 * scale, // Largura do gameplay escalado
          height: 1080 * scale, // Altura do gameplay escalado
          left: -(1920 * scale - width) / 2, // Centrar horizontalmente
          top: cropOffsetY * scale, // Offset Y configurável
          objectFit: "cover",
        }}
        muted
      />
    </AbsoluteFill>
  );
};

export const SceneRenderer: React.FC<SceneRendererProps> = ({
  cena,
  startFrame,
  durationInFrames,
}) => {
  const { fps } = useVideoConfig();

  // Estilo visual: ken_burns (default), vox_motion, ou gameplay_bg
  const estiloVisual = cena.estilo_visual || "ken_burns";

  // Para vox_motion, não precisa de asset_resolvido_path
  if (estiloVisual === "ken_burns" && !cena.asset_resolvido_path) {
    return null;
  }

  // Para gameplay_bg, também precisa de asset_resolvido_path
  if (estiloVisual === "gameplay_bg" && !cena.asset_resolvido_path) {
    return null;
  }

  const isVideo = cena.midia.tipo_asset_preferencial === "video";

  // Fase 9.4 — Offset Y para crop de gameplay (default: 0, centrado)
  const cropOffsetY = cena.crop_offset_y ?? 0;

  return (
    <Sequence from={startFrame} durationInFrames={durationInFrames}>
      <AbsoluteFill>
        {/* Renderizar baseado no estilo visual */}
        {estiloVisual === "vox_motion" ? (
          // Estilo Vox Motion Graphics
          renderElementoGrafico(cena.elemento_grafico, durationInFrames)
        ) : estiloVisual === "gameplay_bg" ? (
          // Fase 9.4 — Estilo gameplay_bg com crop vertical
          <GameplayBgRenderer
            src={cena.asset_resolvido_path!}
            cropOffsetY={cropOffsetY}
          />
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
