/**
 * Emit Williams walk + character geometry + expression as JSON (ESM import).
 * stdin: { emotion?: string, steps?: number }
 */
import { readFileSync } from "node:fs";

let raw = "{}";
try {
  raw = readFileSync(0, "utf8") || "{}";
} catch {
  raw = "{}";
}
const input = JSON.parse(raw || "{}");
const emotion = String(input.emotion || "neutral");
const steps = Math.max(1, Math.min(4, Number(input.steps || 2)));

const empty = {
  ok: false,
  fps: 24,
  totalFrames: 24,
  keyframes: [],
  expression: { emotion, brows: 0, mouth: 0, eyesOpen: 1, faceSy: 0 },
  williams_character: false,
};

try {
  const w = await import("williams-animation-rules");
  const walkEngine = new w.WilliamsWalkEngine();
  const charEngine = new w.WilliamsCharacterEngine();
  const walk = walkEngine.generateBriskTwelveFrameWalk({ stepCount: steps });
  const cycle = charEngine.applyToWalk(walk);
  const fps = w.UNIVERSAL_FPS || 24;

  let expression = {
    emotion,
    brows: 0,
    mouth: 0,
    eyesOpen: 1,
    faceSy: 0,
  };
  try {
    if (typeof w.resolvePose === "function") {
      expression = { ...expression, ...w.resolvePose(emotion) };
    } else if (w.WilliamsActingEngine) {
      const acting = new w.WilliamsActingEngine();
      if (typeof acting.resolvePose === "function") {
        expression = { ...expression, ...acting.resolvePose(emotion) };
      }
    }
  } catch {
    // defaults
  }

  const keyframes = (cycle.keyframes || []).map((kf) => {
    const j = kf.joints || {};
    const g = kf.geometry || {};
    const base = kf.base || {};
    return {
      frame: Number(base.timing?.frame ?? kf.timing?.frame ?? 0),
      phase: base.phase || kf.phase || "contact",
      joints: {
        pelvisY: Number(j.pelvisY || 0),
        hipsRotZ: Number(j.hipsRotZ || 0),
        shouldersRotZ: Number(j.shouldersRotZ || 0),
        leftLegStride: Number(j.leftLegStride || 0),
        rightLegStride: Number(j.rightLegStride || 0),
        leftKneeBend: Number(j.leftKneeBend || 0),
        rightKneeBend: Number(j.rightKneeBend || 0),
        leftArmSwing: Number(j.leftArmSwing || 0),
        rightArmSwing: Number(j.rightArmSwing || 0),
        headY: Number(j.headY || 0),
        beltTiltDeg: Number(g.beltLineTiltDeg || 0),
        shoulderTiltDeg: Number(g.shoulderLineTiltDeg || 0),
      },
    };
  });

  process.stdout.write(
    JSON.stringify({
      ok: true,
      fps,
      totalFrames: Number(cycle.totalFrames || walk.totalFrames || 24),
      keyframes,
      expression,
      williams_character: true,
    })
  );
} catch (err) {
  empty.error = String(err && err.message ? err.message : err);
  process.stdout.write(JSON.stringify(empty));
}
