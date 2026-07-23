import React from "react";
import { Img, interpolate, staticFile, useCurrentFrame } from "remotion";
import { rigSway, type CharacterRigData } from "./CharacterRig";

export type LayerPaths = {
  body?: string | null;
  head?: string | null;
  hand?: string | null;
};

type Props = {
  layers: LayerPaths;
  rig?: CharacterRigData | null;
  width: number;
  height: number;
  accent: string;
};

/**
 * Fixed-identity layered character: body + head (+ optional hand).
 * Joint sway from shotRig drives head offset; keeps one visual identity.
 */
export const CharacterLayers: React.FC<Props> = ({
  layers,
  rig,
  width,
  height,
  accent,
}) => {
  const frame = useCurrentFrame();
  const sway = rigSway(rig || undefined, frame);
  const headBob = interpolate(sway.translateY, [-8, 8], [-6, 6], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const resolve = (p?: string | null) => {
    if (!p) return null;
    if (p.startsWith("http")) return p;
    return staticFile(p.replace(/^public\//, ""));
  };
  const body = resolve(layers.body);
  const head = resolve(layers.head);
  const hand = resolve(layers.hand);
  if (!body && !head) return null;

  return (
    <div
      style={{
        width,
        height,
        position: "relative",
        transform: `translateY(${sway.translateY}px) rotate(${sway.rotate}deg) scaleY(${sway.scaleY})`,
      }}
    >
      {body ? (
        <Img
          src={body}
          style={{
            position: "absolute",
            left: "10%",
            bottom: 0,
            width: "80%",
            height: "78%",
            objectFit: "contain",
          }}
        />
      ) : null}
      {head ? (
        <Img
          src={head}
          style={{
            position: "absolute",
            left: "22%",
            top: Math.max(0, 4 + headBob),
            width: "56%",
            height: "32%",
            objectFit: "contain",
            filter: `drop-shadow(0 4px 8px ${accent}44)`,
          }}
        />
      ) : null}
      {hand ? (
        <Img
          src={hand}
          style={{
            position: "absolute",
            right: "8%",
            bottom: "28%",
            width: "28%",
            height: "22%",
            objectFit: "contain",
            transform: `rotate(${sway.rotate * 1.4}deg)`,
          }}
        />
      ) : null}
    </div>
  );
};
