// Original Daydream artwork; no external font, screensaver, or animation process.
const GLYPHS = {
  D: ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
  A: ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
  Y: ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
  R: ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
  E: ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
  M: ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
};

export const TAGLINE = "Dream it. Make it playable.";
export const LOGO = Array.from({ length: 7 }, (_, row) =>
  [..."DAYDREAM"].map((letter) => GLYPHS[letter][row].replaceAll("1", "█").replaceAll("0", " ")).join(" "),
);
export const DURATION_MS = 2400;
const REVEAL_MS = 1500;
const FRAME_MS = 50;

export function frame(progress, width = 80, height = 24) {
  width = Math.max(0, Math.floor(Number.isFinite(width) ? width : 80));
  height = Math.max(0, Math.floor(Number.isFinite(height) ? height : 24));
  progress = Math.max(0, Math.min(1, Number.isFinite(progress) ? progress : 1));
  if (!width || !height) return "";
  const compact = width < 55 || height < 16;
  const lines = compact
    ? ["✦ DAYDREAM ✦", TAGLINE]
    : ["·       ✦                           ✧       ·", "", ...LOGO, "", TAGLINE];
  const canvasWidth = Math.min(width, Math.max(...lines.map((line) => [...line].length)));
  const beam = Math.floor(progress * canvasWidth);
  return lines.slice(0, height).map((line, y) => {
    const cells = [...line.padEnd(canvasWidth)].slice(0, canvasWidth);
    return cells.map((character, x) => {
      if (progress >= 1 || x < beam) return character;
      // A steady laser sweeps left-to-right, etching the finished artwork behind it.
      // The beam traverses blank rows too; sparks are deterministic, not flicker.
      if (x === beam) return character === " " ? "┃" : "╋";
      if (x === beam + 1 && (y * 7 + beam) % 5 === 0) return "✦";
      return " ";
    }).join("").trimEnd();
  }).join("\n");
}

export function shouldStart(session, route, seen) {
  return Boolean(
    session && !session.parentID && session.agent === "daydream" &&
    route?.type === "session" && route.sessionID === session.id && !seen.includes(session.id),
  );
}

// Small, injectable clock keeps timing/cancellation testable without OpenCode.
export function createPlayback({
  onFrame, onHide,
  now = () => performance.now(),
  schedule = (callback, delay) => setTimeout(callback, delay),
  cancel = (timer) => clearTimeout(timer),
}) {
  let timer;
  let active = false;
  let generation = 0;

  function stop() {
    generation++;
    if (timer !== undefined) cancel(timer);
    timer = undefined;
    if (active) onHide();
    active = false;
  }

  function start({ reducedMotion = false } = {}) {
    stop();
    active = true;
    const ownGeneration = generation;
    const started = now();
    const tick = () => {
      if (!active || ownGeneration !== generation) return;
      const elapsed = now() - started;
      if (elapsed >= DURATION_MS) {
        stop();
        return;
      }
      onFrame(reducedMotion ? 1 : Math.min(1, elapsed / REVEAL_MS));
      timer = schedule(tick, reducedMotion ? DURATION_MS : FRAME_MS);
    };
    tick();
  }

  return { start, stop };
}
