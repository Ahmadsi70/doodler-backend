/**
 * Read timing JSON from stdin; enrich frames via williams-animation-rules (ESM).
 * Portable: WILLIAMS_RULES_PATH → package root, else node_modules import.
 */
import { readFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

function secondsToFramesFallback(sec, fps = 24) {
  return Math.max(12, Math.round(Number(sec) * fps));
}

async function loadWilliams() {
  const env = (process.env.WILLIAMS_RULES_PATH || "").trim();
  if (env) {
    const roots = [
      path.join(env, "dist", "index.js"),
      path.join(env, "index.js"),
      path.join(env, "src", "index.js"),
    ];
    for (const candidate of roots) {
      try {
        return await import(pathToFileURL(candidate).href);
      } catch {
        /* try next */
      }
    }
  }
  return import("williams-animation-rules");
}

const raw = readFileSync(0, "utf8");
const timing = JSON.parse(raw || "{}");
const shots = Array.isArray(timing.shots) ? timing.shots : [];

let UNIVERSAL_FPS = 24;
let secToFrames = secondsToFramesFallback;
let anticipationFor = () => 6;
let usedWilliams = false;

try {
  const w = await loadWilliams();
  UNIVERSAL_FPS = w.UNIVERSAL_FPS || 24;
  if (typeof w.secondsToFrames === "function") {
    secToFrames = (s) => w.secondsToFrames(Number(s));
    usedWilliams = true;
  }
  if (typeof w.defaultAnticipationFrames === "function") {
    anticipationFor = () => {
      try {
        return Math.max(4, Number(w.defaultAnticipationFrames()) || 6);
      } catch {
        return 6;
      }
    };
    usedWilliams = true;
  }
} catch {
  // fallback arithmetic
}

timing.fps = UNIVERSAL_FPS;
timing.shots = shots.map((s) => {
  const sec = Number(s.duration_sec ?? 3);
  const duration_frames = secToFrames(sec, UNIVERSAL_FPS);
  const anticipation_frames = Math.max(
    4,
    Number(s.anticipation_frames ?? anticipationFor())
  );
  const hold_frames = Math.min(
    24,
    Math.max(12, Number(s.hold_frames ?? Math.round(UNIVERSAL_FPS * 0.5)))
  );
  return {
    ...s,
    duration_sec: sec,
    duration_frames,
    hold_frames,
    anticipation_frames,
  };
});
timing.williams_enriched = usedWilliams;
process.stdout.write(JSON.stringify(timing));
