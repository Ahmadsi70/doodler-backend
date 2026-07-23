import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { CharacterLayers, type LayerPaths } from "./CharacterLayers";
import { CharacterRig, rigSway, type CharacterRigData } from "./CharacterRig";

export type CraftHints = {
  id?: string;
  do?: string[];
  dont?: string[];
  rig?: { pose?: string; expression?: string };
  actionBias?: string;
};

export type EnvProfile = {
  mood?: string;
  haze?: number;
  lightShaft?: boolean;
  groundStrength?: number;
  vignette?: number;
  horizonY?: number;
  lighting?: string;
  parallax?: number;
  depthLayers?: number;
};

export type StoryShot = {
  shotId?: number;
  title: string;
  action: string;
  durationSec: number;
  durationFrames: number;
  holdFrames?: number;
  anticipationFrames?: number;
  lens?: string;
  camera?: string;
  cameraMove?: { id?: string; translate_x?: number; scale_end?: number };
  cameraCurve?: {
    move_id?: string;
    keyframes?: Array<{
      frame: number;
      scale: number;
      tx: number;
      ty?: number;
      ease?: string;
    }>;
  } | null;
  expressionCurve?: Array<{
    frame: number;
    eyesOpen?: number;
    brows?: number;
    mouth?: number;
  }> | null;
  composition?: string;
  lighting?: string;
  thirdsX?: number;
  lookSpace?: string;
  verb?: string;
  storyBeat?: string;
  craftHints?: CraftHints | null;
  envProfile?: EnvProfile | null;
  shotRig?: CharacterRigData | null;
  look?: {
    gradeId?: string;
    palette?: StoryPalette;
    vignette?: number;
    grain?: number;
    lutStrength?: number;
    contrast?: number;
    parallax?: number;
    depthLayers?: number;
  } | null;
  shotSize?: string;
  shotSizeScale?: number;
  blinkEveryFrames?: number;
  captionMode?: "hero" | "lower_third" | "hidden";
  transitionIn?: {
    id?: string;
    frames?: number;
    opacity?: boolean;
    slide?: boolean;
  };
};

export type StoryPalette = {
  bg0: string;
  bg1: string;
  bg2: string;
  accent: string;
  text: string;
  muted: string;
};

export type StoryProps = {
  title: string;
  fps: number;
  visualVersion?: number;
  styleId?: string;
  grade?: string;
  pace?: string;
  cameraPreset?: string;
  palette?: StoryPalette;
  continuity?: {
    lineSide?: string;
    approved?: boolean;
    violations?: string[];
    graph?: Record<string, unknown>;
  };
  characterPath?: string | null;
  characterRig?: CharacterRigData | null;
  characterLayers?: LayerPaths | null;
  audioTimeline?: {
    schema?: string;
    fps?: number;
    events?: Array<{
      cue?: string;
      file?: string;
      startFrame?: number;
      gainDb?: number;
      loop?: boolean;
    }>;
    totalFrames?: number;
  };
  shots: StoryShot[];
};

const DEFAULT_PALETTE: StoryPalette = {
  bg0: "#e8dfe8",
  bg1: "#c5d4e8",
  bg2: "#9eb8d4",
  accent: "#7a9eb8",
  text: "#2a3344",
  muted: "#5a6a7a",
};

export const defaultStoryProps: StoryProps = {
  title: "Story",
  fps: 24,
  visualVersion: 2,
  styleId: "symmetrical_pastel_cinema",
  grade: "pastel_muted",
  pace: "measured",
  cameraPreset: "locked_symmetric",
  palette: DEFAULT_PALETTE,
  continuity: { lineSide: "left", approved: true, violations: [] },
  characterPath: null,
  shots: [
    {
      shotId: 0,
      title: "Shot 1",
      action: "A character enters and looks toward the light.",
      durationSec: 3,
      durationFrames: 72,
      holdFrames: 12,
      anticipationFrames: 6,
      lens: "standard",
      camera: "static",
      composition: "C",
      thirdsX: 0.5,
      lookSpace: "center",
      craftHints: { rig: { pose: "walk", expression: "neutral" }, actionBias: "even" },
      envProfile: { mood: "soft", haze: 0.22, lightShaft: true, groundStrength: 0.55, vignette: 0.25, horizonY: 0.62 },
    },
    {
      shotId: 1,
      title: "Shot 2",
      action: "Then they react in shock because hope returns.",
      durationSec: 3.5,
      durationFrames: 84,
      lens: "action",
      camera: "motivated_push",
      composition: "L",
      thirdsX: 0.33,
      lookSpace: "right",
      craftHints: { rig: { pose: "react", expression: "shock" }, actionBias: "slow_in" },
      envProfile: { mood: "tense", haze: 0.35, lightShaft: true, groundStrength: 0.55, vignette: 0.4, horizonY: 0.62 },
    },
  ],
};

const CROSSFADE_FRAMES = 12;

const lensScale = (lens?: string) => {
  if (lens === "action") return 1.08;
  if (lens === "beauty") return 0.94;
  return 1;
};

const applyEase = (u: number, ease?: string) => {
  const t = Math.max(0, Math.min(1, u));
  switch (ease) {
    case "ease_in":
      return t * t;
    case "ease_out":
      return 1 - (1 - t) * (1 - t);
    case "ease_in_out":
      return t * t * (3 - 2 * t);
    case "hold":
      return 0;
    default:
      return t;
  }
};

/** Sample CameraCurveAgent keyframes at local shot frame. */
const sampleCameraCurve = (
  curve: StoryShot["cameraCurve"] | null | undefined,
  frame: number,
): { scale: number; tx: number; ty: number } | null => {
  const kfs = curve?.keyframes;
  if (!kfs || kfs.length < 2) return null;
  const sorted = [...kfs].sort((a, b) => a.frame - b.frame);
  if (frame <= sorted[0].frame) {
    return { scale: sorted[0].scale, tx: sorted[0].tx, ty: sorted[0].ty ?? 0 };
  }
  const last = sorted[sorted.length - 1];
  if (frame >= last.frame) {
    return { scale: last.scale, tx: last.tx, ty: last.ty ?? 0 };
  }
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (frame >= a.frame && frame <= b.frame) {
      const span = Math.max(1, b.frame - a.frame);
      const u = applyEase((frame - a.frame) / span, a.ease);
      return {
        scale: a.scale + (b.scale - a.scale) * u,
        tx: a.tx + (b.tx - a.tx) * u,
        ty: (a.ty ?? 0) + ((b.ty ?? 0) - (a.ty ?? 0)) * u,
      };
    }
  }
  return { scale: last.scale, tx: last.tx, ty: last.ty ?? 0 };
};

/** Sample ActingLead expression curve at local shot frame. */
const sampleExpressionCurve = (
  curve: StoryShot["expressionCurve"] | null | undefined,
  frame: number,
): { eyesOpen: number; brows: number; mouth: number } | null => {
  if (!curve || curve.length < 2) return null;
  const sorted = [...curve].sort((a, b) => a.frame - b.frame);
  const lerp = (a: number, b: number, u: number) => a + (b - a) * u;
  if (frame <= sorted[0].frame) {
    return {
      eyesOpen: Number(sorted[0].eyesOpen ?? 1),
      brows: Number(sorted[0].brows ?? 0),
      mouth: Number(sorted[0].mouth ?? 0),
    };
  }
  const last = sorted[sorted.length - 1];
  if (frame >= last.frame) {
    return {
      eyesOpen: Number(last.eyesOpen ?? 1),
      brows: Number(last.brows ?? 0),
      mouth: Number(last.mouth ?? 0),
    };
  }
  for (let i = 0; i < sorted.length - 1; i++) {
    const a = sorted[i];
    const b = sorted[i + 1];
    if (frame >= a.frame && frame <= b.frame) {
      const span = Math.max(1, b.frame - a.frame);
      const u = (frame - a.frame) / span;
      return {
        eyesOpen: lerp(Number(a.eyesOpen ?? 1), Number(b.eyesOpen ?? 1), u),
        brows: lerp(Number(a.brows ?? 0), Number(b.brows ?? 0), u),
        mouth: lerp(Number(a.mouth ?? 0), Number(b.mouth ?? 0), u),
      };
    }
  }
  return {
    eyesOpen: Number(last.eyesOpen ?? 1),
    brows: Number(last.brows ?? 0),
    mouth: Number(last.mouth ?? 0),
  };
};

/** Multiplane environment: sky band, haze, ground, optional light shaft, vignette. */
const EnvironmentLayers: React.FC<{
  palette: StoryPalette;
  env?: EnvProfile | null;
  thirdsX: number;
  frame: number;
  dur: number;
  width: number;
  height: number;
}> = ({ palette, env, thirdsX, frame, dur, width, height }) => {
  const mood = env?.mood || "neutral";
  const haze = env?.haze ?? 0.2;
  const horizon = env?.horizonY ?? 0.62;
  const ground = env?.groundStrength ?? 0.5;
  const vig = env?.vignette ?? 0.28;
  const depthN = Math.max(2, Math.min(5, Number(env?.depthLayers ?? 3)));
  const paraAmt = Number(env?.parallax ?? 0.5);
  const parallax = interpolate(frame, [0, dur], [-40 * paraAmt, 40 * paraAmt], {
    extrapolateRight: "clamp",
  });
  const tense = mood === "tense" || mood === "drama";
  const skyTop = tense ? palette.bg2 : palette.bg1;
  const skyBot = tense ? palette.bg0 : palette.bg0;

  const depthPlanes = Array.from({ length: depthN }, (_, i) => {
    const u = i / Math.max(1, depthN - 1);
    return {
      opacity: 0.08 + u * 0.12,
      shift: parallax * (0.1 + u * 0.55),
      top: `${horizon * (0.35 + u * 0.4) * 100}%`,
    };
  });

  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      {/* Far sky / wall wash */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `linear-gradient(180deg, ${skyTop} 0%, ${skyBot} ${horizon * 100}%, ${palette.bg2} 100%)`,
        }}
      />
      {depthPlanes.map((p, i) => (
        <div
          key={`depth-${i}`}
          style={{
            position: "absolute",
            left: -60,
            right: -60,
            top: p.top,
            height: "28%",
            background: `radial-gradient(ellipse at ${Math.round(thirdsX * 100)}% 50%, ${palette.bg1} 0%, transparent 72%)`,
            opacity: p.opacity + haze * 0.25,
            transform: `translateX(${p.shift}px)`,
          }}
        />
      ))}
      {/* Soft atmospheric haze plane */}
      <div
        style={{
          position: "absolute",
          left: -40,
          right: -40,
          top: `${horizon * 40}%`,
          height: "45%",
          background: `radial-gradient(ellipse at ${Math.round(thirdsX * 100)}% 40%, ${palette.bg1} 0%, transparent 70%)`,
          opacity: haze,
          transform: `translateX(${parallax * 0.35}px)`,
        }}
      />
      {/* Mid ground silhouette band */}
      <div
        style={{
          position: "absolute",
          left: 0,
          right: 0,
          top: `${horizon * 100}%`,
          height: `${(1 - horizon) * 100}%`,
          background: `linear-gradient(180deg, ${palette.muted}33 0%, ${palette.bg2}cc 55%, ${palette.bg0} 100%)`,
          opacity: 0.55 + ground * 0.35,
          transform: `translateX(${parallax * 0.15}px)`,
        }}
      />
      {/* Ground contact ellipse */}
      <div
        style={{
          position: "absolute",
          left: width * (thirdsX - 0.18),
          bottom: height * 0.12,
          width: width * 0.34,
          height: 36,
          borderRadius: "50%",
          background: palette.muted,
          opacity: 0.18 + ground * 0.2,
          filter: "blur(2px)",
        }}
      />
      {env?.lightShaft ? (
        <div
          style={{
            position: "absolute",
            left: `${Math.round(thirdsX * 100)}%`,
            top: "-10%",
            width: width * 0.28,
            height: "70%",
            marginLeft: -width * 0.14,
            background: `linear-gradient(180deg, ${palette.accent}55 0%, transparent 80%)`,
            opacity: 0.35,
            transform: `skewX(-12deg) translateX(${parallax * 0.2}px)`,
            filter: "blur(8px)",
          }}
        />
      ) : null}
      {/* Vignette */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: `radial-gradient(ellipse at center, transparent 42%, #000 ${100 - vig * 40}%)`,
          opacity: vig,
          mixBlendMode: "multiply",
        }}
      />
    </AbsoluteFill>
  );
};

/** Film grain + mild LUT contrast wash driven by look bible. */
const FilmLookOverlay: React.FC<{
  grain?: number;
  lutStrength?: number;
  contrast?: number;
  frame: number;
}> = ({ grain = 0.1, lutStrength = 0.15, contrast = 1.05, frame }) => {
  const g = Math.max(0, Math.min(0.45, grain));
  const lut = Math.max(0, Math.min(0.5, lutStrength));
  const flicker = 0.85 + 0.15 * Math.sin(frame * 0.7);
  return (
    <AbsoluteFill style={{ pointerEvents: "none" }}>
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: g * flicker,
          mixBlendMode: "overlay",
          backgroundImage:
            "repeating-radial-gradient(circle at 20% 30%, #fff 0 0.5px, transparent 1px 3px), repeating-radial-gradient(circle at 70% 60%, #000 0 0.4px, transparent 1px 4px)",
          backgroundSize: "120px 120px, 90px 90px",
          backgroundPosition: `${(frame * 3) % 40}px ${(frame * 2) % 30}px`,
        }}
      />
      <div
        style={{
          position: "absolute",
          inset: 0,
          opacity: lut,
          mixBlendMode: "soft-light",
          background: `linear-gradient(160deg, #ffe8d0 0%, transparent 45%, #c8d8f0 100%)`,
          filter: `contrast(${contrast})`,
        }}
      />
    </AbsoluteFill>
  );
};

/**
 * Pro 2D stage v2: environment layers + craft pose rig + stronger transitions.
 */
const ShotStage: React.FC<{
  shot: StoryShot;
  characterSrc?: string | null;
  characterRig?: CharacterRigData | null;
  characterLayers?: LayerPaths | null;
  brand: string;
  palette: StoryPalette;
  lineSide: string;
  pace: string;
  isFirst: boolean;
  isLast: boolean;
}> = ({
  shot,
  characterSrc,
  characterRig,
  characterLayers,
  brand,
  palette,
  lineSide,
  pace,
  isFirst,
  isLast,
}) => {
  const frame = useCurrentFrame();
  const { fps, width, height } = useVideoConfig();
  const activeRig = shot.shotRig?.keyframes?.length
    ? shot.shotRig
    : characterRig;
  const pose = shot.craftHints?.rig?.pose || "idle";
  const expression = shot.craftHints?.rig?.expression;
  const sway = rigSway(activeRig, frame);
  const ant = Math.max(0, shot.anticipationFrames ?? 6);
  const hold = Math.max(0, shot.holdFrames ?? 12);
  const dur = shot.durationFrames || Math.round((shot.durationSec || 3) * fps);
  const actionStart = ant;
  const holdStart = Math.max(actionStart + 1, dur - hold);

  const antPull = interpolate(frame, [0, ant], [1, 0.96], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const enter = spring({
    frame: Math.max(0, frame - ant),
    fps,
    config: {
      damping: pace === "chase_punch" || pace === "panel_punch" ? 140 : 200,
      mass: 0.85,
    },
  });
  const push =
    shot.camera === "motivated_push" || shot.cameraMove?.id === "motivated_push"
      ? interpolate(
          frame,
          [actionStart, holdStart],
          [1, Number(shot.cameraMove?.scale_end ?? 1.14)],
          {
            extrapolateLeft: "clamp",
            extrapolateRight: "clamp",
          },
        )
      : interpolate(
          frame,
          [0, dur],
          [1, Number(shot.cameraMove?.scale_end ?? 1)],
          { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
        );
  const breath =
    frame >= holdStart
      ? Math.sin(((frame - holdStart) / Math.max(1, hold)) * Math.PI) * 4
      : 0;
  const driftDir = lineSide === "right" ? -1 : 1;
  const moveX = Number(shot.cameraMove?.translate_x ?? 0);
  const drift =
    shot.camera === "static" && moveX === 0
      ? breath
      : interpolate(frame, [0, dur], [0, (moveX || 28) * driftDir], {
          extrapolateRight: "clamp",
        }) + breath;

  const camSample = sampleCameraCurve(shot.cameraCurve, frame);
  const pushFinal = camSample ? camSample.scale : push;
  const driftFinal = camSample
    ? camSample.tx * driftDir + breath
    : drift;

  const bias = shot.craftHints?.actionBias || "even";
  const biasEase =
    bias === "slow_in" ? enter * enter : bias === "slow_out" ? Math.sqrt(enter) : enter;
  const stageScale =
    lensScale(shot.lens) *
    pushFinal *
    (frame < ant ? antPull : 1) *
    (0.96 + biasEase * 0.04);
  const craftAlive =
    (shot.craftHints?.dont || []).some((d) => /freeze|dead|static/i.test(d))
      ? Math.sin(frame / 10) * 1.8
      : Math.sin(frame / 14) * 0.6;

  const thirdsX = shot.thirdsX ?? 0.5;
  const charOnLeft = thirdsX <= 0.45;
  const padX = Math.round(width * 0.06);
  const rowDir = charOnLeft ? "row" : "row-reverse";

  // Per-shot transition grammar (fallback CROSSFADE_FRAMES)
  const edge = Math.min(
    Math.max(2, shot.transitionIn?.frames ?? CROSSFADE_FRAMES),
    Math.floor(dur / 3),
  );
  const useSlide = shot.transitionIn?.slide !== false;
  const fadeIn = isFirst
    ? 1
    : interpolate(frame, [0, edge], [0, 1], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
  const fadeOut = isLast
    ? interpolate(frame, [Math.max(0, dur - edge), dur], [1, 0.2], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      })
    : interpolate(frame, [Math.max(0, dur - edge), dur], [1, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
  const slideIn = isFirst || !useSlide
    ? 0
    : interpolate(frame, [0, edge], [40 * driftDir, 0], {
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
  const shotOpacity = fadeIn * fadeOut;

  const exprSample = sampleExpressionCurve(shot.expressionCurve, frame);
  const exprOverride = expression
    ? {
        emotion: expression,
        ...(expression === "shock"
          ? { brows: 0.85, mouth: 0.7, eyesOpen: 0.35 }
          : expression === "hope"
            ? { brows: -0.2, mouth: 0.35, eyesOpen: 1 }
            : expression === "worry"
              ? { brows: 0.45, mouth: -0.25, eyesOpen: 0.75 }
              : {}),
        ...(exprSample || {}),
      }
    : exprSample
      ? { ...exprSample }
      : undefined;

  const captionMode = shot.captionMode || "lower_third";
  const showHeroText = captionMode === "hero";
  const showLowerThird = captionMode === "lower_third";
  const shotPalette = shot.look?.palette || palette;
  const sizeScale = Number(shot.shotSizeScale ?? 1);

  return (
    <AbsoluteFill style={{ opacity: shotOpacity }}>
      <EnvironmentLayers
        palette={shotPalette}
        env={shot.envProfile}
        thirdsX={thirdsX}
        frame={frame}
        dur={dur}
        width={width}
        height={height}
      />
      <FilmLookOverlay
        grain={Number(shot.look?.grain ?? 0.1)}
        lutStrength={Number(shot.look?.lutStrength ?? 0.15)}
        contrast={Number(shot.look?.contrast ?? 1.05)}
        frame={frame}
      />
      <div
        style={{
          position: "absolute",
          top: 40,
          left: 56,
          color: shotPalette.accent,
          fontSize: 22,
          letterSpacing: 3,
          fontFamily: "Georgia, 'Times New Roman', serif",
          textTransform: "uppercase",
          opacity: 0.85,
        }}
      >
        {brand}
      </div>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: rowDir as "row" | "row-reverse",
          alignItems: "center",
          justifyContent: showHeroText ? "space-between" : "center",
          gap: 48,
          padding: `100px ${padX}px`,
          transform: `translate(${driftFinal + slideIn}px, ${breath * 0.35 + craftAlive}px) scale(${stageScale * sizeScale})`,
        }}
      >
        <div
          style={{
            flex: "0 0 auto",
            marginLeft: charOnLeft
              ? Math.max(0, width * thirdsX - width * 0.2)
              : undefined,
            marginRight: !charOnLeft
              ? Math.max(0, width * (1 - thirdsX) - width * 0.2)
              : undefined,
          }}
        >
          {characterLayers && (characterLayers.body || characterLayers.head) ? (
            <CharacterLayers
              layers={characterLayers}
              rig={activeRig}
              width={Math.min(420, width * 0.28)}
              height={Math.min(640, height * 0.7)}
              accent={shotPalette.accent}
            />
          ) : characterSrc ? (
            <Img
              src={characterSrc}
              style={{
                width: Math.min(480, width * 0.26),
                height: Math.min(680, height * 0.68),
                objectFit: "cover",
                borderRadius: 4,
                boxShadow: `0 28px 72px ${shotPalette.muted}77`,
                border: `1px solid ${shotPalette.accent}66`,
                transform: `translateY(${sway.translateY}px) rotate(${sway.rotate}deg) scaleY(${
                  (frame < ant ? 0.97 + (1 - antPull) * 0.5 : 1) * sway.scaleY
                })`,
              }}
            />
          ) : activeRig?.keyframes?.length ? (
            <div
              style={{
                width: 300,
                height: 440,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                borderRadius: 6,
                background: `linear-gradient(165deg, ${shotPalette.bg1}cc, ${shotPalette.bg2}aa)`,
                border: `1px solid ${shotPalette.accent}99`,
                boxShadow: `0 20px 48px ${shotPalette.muted}44`,
              }}
            >
              <CharacterRig
                rig={activeRig}
                accent={shotPalette.accent}
                muted={shotPalette.muted}
                width={270}
                height={410}
                pose={pose}
                expressionOverride={exprOverride}
                blinkEveryFrames={shot.blinkEveryFrames ?? 36}
              />
            </div>
          ) : (
            <div
              style={{
                width: 260,
                height: 400,
                borderRadius: 6,
                background: `linear-gradient(165deg, ${shotPalette.bg1}, ${shotPalette.bg2})`,
                border: `1px solid ${shotPalette.accent}88`,
                boxShadow: `inset 0 0 40px ${shotPalette.accent}33`,
                transform: frame < ant ? `scaleY(0.97)` : undefined,
              }}
            />
          )}
        </div>
        <div
          style={{
            flex: "1 1 auto",
            maxWidth: showHeroText ? 780 : 0,
            color: shotPalette.text,
            fontFamily: "Georgia, 'Times New Roman', serif",
            textAlign: charOnLeft ? "left" : "right",
            display: showHeroText ? "block" : "none",
          }}
        >
          <div
            style={{
              fontSize: 18,
              color: shotPalette.muted,
              marginBottom: 10,
              letterSpacing: 1.2,
              textTransform: "uppercase",
            }}
          >
            {shot.title}
            {shot.verb ? ` · ${shot.verb}` : ""}
          </div>
          <div style={{ fontSize: 44, lineHeight: 1.28, fontWeight: 600 }}>
            {shot.action}
          </div>
        </div>
      </div>
      {showLowerThird ? (
        <div
          style={{
            position: "absolute",
            left: 48,
            right: 48,
            bottom: 48,
            padding: "16px 22px",
            background: `${shotPalette.bg2}cc`,
            borderTop: `2px solid ${shotPalette.accent}`,
            color: shotPalette.text,
            fontFamily: "Georgia, 'Times New Roman', serif",
          }}
        >
          <div
            style={{
              fontSize: 13,
              letterSpacing: 1.4,
              textTransform: "uppercase",
              color: shotPalette.muted,
              marginBottom: 6,
            }}
          >
            {shot.title}
            {shot.verb ? ` · ${shot.verb}` : ""}
          </div>
          <div style={{ fontSize: 26, lineHeight: 1.35, fontWeight: 600 }}>
            {shot.action}
          </div>
        </div>
      ) : null}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: 10,
          background: `linear-gradient(90deg, transparent, ${shotPalette.accent}, transparent)`,
          opacity: 0.5,
        }}
      />
    </AbsoluteFill>
  );
};

export const StoryNarrative: React.FC<StoryProps> = (props) => {
  const shots = props.shots?.length ? props.shots : defaultStoryProps.shots;
  const palette = props.palette || DEFAULT_PALETTE;
  const lineSide = props.continuity?.lineSide || "left";
  const pace = props.pace || "measured";
  let from = 0;
  let characterSrc: string | null = null;
  if (props.characterPath) {
    characterSrc = props.characterPath.startsWith("http")
      ? props.characterPath
      : staticFile(props.characterPath.replace(/^public\//, ""));
  }
  const audioEvents = props.audioTimeline?.events || [];

  return (
    <AbsoluteFill style={{ backgroundColor: palette.bg0 }}>
      {audioEvents.map((ev, i) => {
        if (!ev.file) return null;
        const vol = Math.pow(10, (Number(ev.gainDb ?? -12) || -12) / 20);
        const src = ev.file.startsWith("http")
          ? ev.file
          : staticFile(String(ev.file).replace(/^public\//, ""));
        return (
          <Sequence
            key={`audio-${i}-${ev.cue}`}
            from={Math.max(0, Number(ev.startFrame) || 0)}
          >
            <Audio src={src} volume={Math.min(1, Math.max(0, vol))} />
          </Sequence>
        );
      })}
      {shots.map((shot, i) => {
        const dur =
          shot.durationFrames || Math.round((shot.durationSec || 3) * 24);
        const overlap =
          i === 0
            ? 0
            : Math.max(2, shot.transitionIn?.frames ?? CROSSFADE_FRAMES);
        const start = Math.max(0, from - overlap);
        const seqDur = dur + overlap;
        from += dur;
        return (
          <Sequence key={i} from={start} durationInFrames={seqDur}>
            <ShotStage
              shot={shot}
              characterSrc={characterSrc}
              characterRig={props.characterRig}
              characterLayers={props.characterLayers}
              brand={props.title || "Story"}
              palette={palette}
              lineSide={lineSide}
              pace={pace}
              isFirst={i === 0}
              isLast={i === shots.length - 1}
            />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
