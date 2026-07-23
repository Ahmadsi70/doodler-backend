import React, { useMemo } from "react";
import { interpolate, useCurrentFrame } from "remotion";

export type RigJoints = {
  pelvisY: number;
  hipsRotZ: number;
  shouldersRotZ: number;
  leftLegStride: number;
  rightLegStride: number;
  leftKneeBend: number;
  rightKneeBend: number;
  leftArmSwing: number;
  rightArmSwing: number;
  headY: number;
  beltTiltDeg?: number;
  shoulderTiltDeg?: number;
};

export type RigKeyframe = {
  frame: number;
  phase?: string;
  joints: RigJoints;
};

export type CharacterRigData = {
  fps?: number;
  totalFrames?: number;
  keyframes: RigKeyframe[];
  expression?: {
    emotion?: string;
    brows?: number;
    mouth?: number;
    eyesOpen?: number;
    faceSy?: number;
  };
  williams_character?: boolean;
};

function sampleJoints(rig: CharacterRigData, frame: number): RigJoints {
  const kfs = rig.keyframes || [];
  if (!kfs.length) {
    return {
      pelvisY: 0,
      hipsRotZ: 0,
      shouldersRotZ: 0,
      leftLegStride: 0,
      rightLegStride: 0,
      leftKneeBend: 0.1,
      rightKneeBend: 0.1,
      leftArmSwing: 0,
      rightArmSwing: 0,
      headY: 0,
    };
  }
  const cycle = Math.max(1, rig.totalFrames || kfs[kfs.length - 1].frame || 24);
  const t = ((frame % cycle) + cycle) % cycle;
  const sorted = [...kfs].sort((a, b) => a.frame - b.frame);
  let i = 0;
  while (i < sorted.length - 1 && sorted[i + 1].frame <= t) i++;
  const a = sorted[i];
  const b = sorted[Math.min(i + 1, sorted.length - 1)];
  const span = Math.max(1, b.frame - a.frame);
  const u = a === b ? 0 : (t - a.frame) / span;
  const lerp = (x: number, y: number) => x + (y - x) * u;
  const ja = a.joints;
  const jb = b.joints;
  return {
    pelvisY: lerp(ja.pelvisY, jb.pelvisY),
    hipsRotZ: lerp(ja.hipsRotZ, jb.hipsRotZ),
    shouldersRotZ: lerp(ja.shouldersRotZ, jb.shouldersRotZ),
    leftLegStride: lerp(ja.leftLegStride, jb.leftLegStride),
    rightLegStride: lerp(ja.rightLegStride, jb.rightLegStride),
    leftKneeBend: lerp(ja.leftKneeBend, jb.leftKneeBend),
    rightKneeBend: lerp(ja.rightKneeBend, jb.rightKneeBend),
    leftArmSwing: lerp(ja.leftArmSwing, jb.leftArmSwing),
    rightArmSwing: lerp(ja.rightArmSwing, jb.rightArmSwing),
    headY: lerp(ja.headY, jb.headY),
    beltTiltDeg: lerp(ja.beltTiltDeg || 0, jb.beltTiltDeg || 0),
    shoulderTiltDeg: lerp(ja.shoulderTiltDeg || 0, jb.shoulderTiltDeg || 0),
  };
}

export type PoseLabel = "idle" | "walk" | "react" | "run" | string;

/** Static joint offsets when craft pose is applied on top of sampled keys. */
export function poseJointBoost(pose?: PoseLabel): Partial<RigJoints> {
  const p = (pose || "idle").toLowerCase();
  if (p === "walk") {
    return {
      leftLegStride: 0.2,
      rightLegStride: -0.15,
      leftArmSwing: -0.15,
      rightArmSwing: 0.15,
      shouldersRotZ: -3,
    };
  }
  if (p === "react") {
    return {
      pelvisY: -0.12,
      shouldersRotZ: 10,
      headY: 0.15,
      leftKneeBend: 0.2,
      rightKneeBend: 0.2,
    };
  }
  if (p === "run") {
    return {
      leftLegStride: 0.35,
      rightLegStride: -0.35,
      leftArmSwing: -0.35,
      rightArmSwing: 0.35,
      pelvisY: 0.1,
    };
  }
  return {};
}

type Props = {
  rig: CharacterRigData;
  accent: string;
  muted: string;
  width?: number;
  height?: number;
  /** Craft pose label — boosts joints for readable acting. */
  pose?: PoseLabel;
  /** Override / merge expression channels. */
  expressionOverride?: CharacterRigData["expression"];
  /** Blink period from performance bible (frames). */
  blinkEveryFrames?: number;
};

/**
 * 2D stick/silhouette rig driven by Williams walk+character joint channels.
 * Used when no photo is provided; also supplies sway for photo mode.
 */
export const CharacterRig: React.FC<Props> = ({
  rig,
  accent,
  muted,
  width = 260,
  height = 400,
  pose,
  expressionOverride,
  blinkEveryFrames = 36,
}) => {
  const frame = useCurrentFrame();
  const j = useMemo(() => {
    const sampled = sampleJoints(rig, frame);
    const boost = poseJointBoost(pose);
    return {
      ...sampled,
      pelvisY: sampled.pelvisY + (boost.pelvisY || 0),
      hipsRotZ: sampled.hipsRotZ + (boost.hipsRotZ || 0),
      shouldersRotZ: sampled.shouldersRotZ + (boost.shouldersRotZ || 0),
      leftLegStride: sampled.leftLegStride + (boost.leftLegStride || 0),
      rightLegStride: sampled.rightLegStride + (boost.rightLegStride || 0),
      leftKneeBend: sampled.leftKneeBend + (boost.leftKneeBend || 0),
      rightKneeBend: sampled.rightKneeBend + (boost.rightKneeBend || 0),
      leftArmSwing: sampled.leftArmSwing + (boost.leftArmSwing || 0),
      rightArmSwing: sampled.rightArmSwing + (boost.rightArmSwing || 0),
      headY: sampled.headY + (boost.headY || 0),
      beltTiltDeg: (sampled.beltTiltDeg || 0) + (boost.beltTiltDeg || 0),
      shoulderTiltDeg:
        (sampled.shoulderTiltDeg || 0) + (boost.shoulderTiltDeg || 0),
    };
  }, [rig, frame, pose]);
  const expr = { ...(rig.expression || {}), ...(expressionOverride || {}) };
  const period = Math.max(12, blinkEveryFrames);
  const blinkPhase = frame % period;
  const blink =
    blinkPhase <= 1
      ? 0.15
      : blinkPhase === 2
        ? 0.55
        : Number(expr.eyesOpen ?? 1);
  const eyesOpen = Math.min(Number(expr.eyesOpen ?? 1), blink);
  const cx = width / 2;
  const pelvisY = height * 0.52 - j.pelvisY * 40;
  const headY = height * 0.18 - j.headY * 30;
  const shoulderY = height * 0.32;
  const hipY = pelvisY;
  const strideScale = 36;
  const kneeDrop = 28;
  const armScale = 40;

  const lHip = { x: cx - 18, y: hipY };
  const rHip = { x: cx + 18, y: hipY };
  const lShoulder = {
    x: cx - 28 + j.shouldersRotZ * 0.4,
    y: shoulderY + (j.shoulderTiltDeg || 0) * 0.3,
  };
  const rShoulder = {
    x: cx + 28 - j.shouldersRotZ * 0.4,
    y: shoulderY - (j.shoulderTiltDeg || 0) * 0.3,
  };
  const lKnee = {
    x: lHip.x + j.leftLegStride * strideScale,
    y: lHip.y + 50 + j.leftKneeBend * kneeDrop,
  };
  const rKnee = {
    x: rHip.x + j.rightLegStride * strideScale,
    y: rHip.y + 50 + j.rightKneeBend * kneeDrop,
  };
  const lFoot = {
    x: lKnee.x + j.leftLegStride * 10,
    y: lKnee.y + 55 - j.leftKneeBend * 8,
  };
  const rFoot = {
    x: rKnee.x + j.rightLegStride * 10,
    y: rKnee.y + 55 - j.rightKneeBend * 8,
  };
  const lHand = {
    x: lShoulder.x + j.leftArmSwing * armScale,
    y: lShoulder.y + 70 - Math.abs(j.leftArmSwing) * 10,
  };
  const rHand = {
    x: rShoulder.x + j.rightArmSwing * armScale,
    y: rShoulder.y + 70 - Math.abs(j.rightArmSwing) * 10,
  };
  const mouthOpen = interpolate(Number(expr.mouth || 0), [-1, 1], [2, 10], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const eyeOpen = interpolate(eyesOpen, [0, 1], [1, 4], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const brow = Number(expr.brows || 0) * 3;

  const line = (a: { x: number; y: number }, b: { x: number; y: number }, w = 6) => (
    <line
      x1={a.x}
      y1={a.y}
      x2={b.x}
      y2={b.y}
      stroke={accent}
      strokeWidth={w}
      strokeLinecap="round"
    />
  );

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      <ellipse
        cx={cx}
        cy={height - 18}
        rx={48}
        ry={8}
        fill={muted}
        opacity={0.35}
      />
      {/* torso */}
      {line(
        { x: cx, y: headY + 28 },
        { x: cx + (j.beltTiltDeg || 0) * 0.5, y: hipY },
        10
      )}
      {line(lShoulder, rShoulder, 8)}
      {line(lHip, rHip, 8)}
      {/* arms */}
      {line(lShoulder, lHand, 6)}
      {line(rShoulder, rHand, 6)}
      {/* legs */}
      {line(lHip, lKnee, 7)}
      {line(lKnee, lFoot, 7)}
      {line(rHip, rKnee, 7)}
      {line(rKnee, rFoot, 7)}
      {/* head */}
      <circle cx={cx + Number(expr.faceSy || 0) * 4} cy={headY} r={26} fill={accent} />
      <circle
        cx={cx - 8}
        cy={headY - 2 - brow}
        r={eyeOpen}
        fill={muted}
      />
      <circle
        cx={cx + 8}
        cy={headY - 2 - brow}
        r={eyeOpen}
        fill={muted}
      />
      <ellipse
        cx={cx}
        cy={headY + 10}
        rx={6}
        ry={mouthOpen / 2}
        fill={muted}
      />
    </svg>
  );
};

/** Export joint sample for photo-plate sway transforms. */
export function rigSway(rig: CharacterRigData | null | undefined, frame: number) {
  if (!rig?.keyframes?.length) {
    return { rotate: 0, translateY: 0, scaleY: 1 };
  }
  const j = sampleJoints(rig, frame);
  return {
    rotate: (j.shouldersRotZ || 0) * 0.15 + (j.beltTiltDeg || 0) * 0.1,
    translateY: -j.pelvisY * 12 - j.headY * 6,
    scaleY: 1 + Math.min(0.04, (j.leftKneeBend + j.rightKneeBend) * 0.02),
  };
}
