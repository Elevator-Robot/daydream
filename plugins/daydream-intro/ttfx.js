import { spawn } from "node:child_process";

// ttfx --reuse-canvas emits a complete canvas between restore/save/move-up markers.
// Never send these cursor controls to OpenCode's terminal: only render text/colors.
const FRAME_MARKER = /\x1b8\x1b7\x1b\[\d+A/;
const ANSI = /(\x1b\[[0-?]*[ -/]*[@-~]|\x1b[78]|\x1b\][^\x07]*(?:\x07|\x1b\\))/g;
const MAX_BUFFER = 1024 * 1024;
export const MAX_DURATION_MS = 30000;

export function parseCanvas(payload, width, height) {
  let color = "#ffffff";
  let row = 0;
  let column = 0;
  const segments = [];
  function append(text) {
    if (!text) return;
    const previous = segments.at(-1);
    if (previous?.color === color) previous.text += text;
    else segments.push({ text, color });
  }
  for (const token of payload.split(ANSI)) {
    if (!token) continue;
    if (token.startsWith("\x1b")) {
      const match = /^\x1b\[([\d;]*)m$/.exec(token);
      if (!match) continue;
      const codes = (match[1] || "0").split(";").map(Number);
      for (let i = 0; i < codes.length; i++) {
        if (codes[i] === 0 || codes[i] === 39) color = "#ffffff";
        if (codes[i] === 38 && codes[i + 1] === 2 && codes.length >= i + 5) {
          const rgb = codes.slice(i + 2, i + 5);
          if (rgb.every((value) => value >= 0 && value <= 255)) {
            color = "#" + rgb.map((value) => value.toString(16).padStart(2, "0")).join("");
          }
          i += 4;
        }
      }
      continue;
    }
    for (const character of token) {
      if (character === "\n") {
        row++;
        column = 0;
        if (row < height) append("\n");
      } else if (!/[\x00-\x1f\x7f-\x9f]/.test(character)) {
        if (row < height && column < width) append(character);
        column++;
      }
    }
  }
  return segments;
}

export function createDecoder(width, height, onFrame) {
  let buffer = "";
  let started = false;
  return {
    push(chunk) {
      buffer += chunk;
      if (buffer.length > MAX_BUFFER) throw new Error("ttfx frame exceeded the safety limit");
      let marker;
      while ((marker = FRAME_MARKER.exec(buffer))) {
        if (started) onFrame(parseCanvas(buffer.slice(0, marker.index), width, height));
        buffer = buffer.slice(marker.index + marker[0].length);
        started = true;
      }
    },
    finish() {
      if (!started) throw new Error("ttfx returned no supported canvas frames");
      if (buffer) onFrame(parseCanvas(buffer, width, height));
      buffer = "";
    },
  };
}

export function createPlayback({
  onFrame, onHide, onError,
  spawnProcess = spawn,
  schedule = setTimeout,
  cancel = clearTimeout,
  executable = "ttfx",
}) {
  let current;

  function stop() {
    const run = current;
    current = undefined;
    if (!run) return;
    cancel(run.timeout);
    if (run.hold !== undefined) cancel(run.hold);
    if (run.child && !run.closed) {
      run.child.kill("SIGTERM");
      run.kill = schedule(() => {
        if (!run.closed) run.child.kill("SIGKILL");
      }, 500);
      run.kill?.unref?.();
    }
    onHide();
  }

  function start({ text, width, height, reducedMotion = false }) {
    stop();
    if (!Number.isInteger(width) || width < 8 || width > 160 ||
        !Number.isInteger(height) || height < 4 || height > 40) {
      onError(new Error("Invalid intro canvas dimensions"));
      return;
    }
    const run = { closed: false };
    current = run;
    const fail = (error) => {
      if (current !== run) return;
      stop();
      onError(error);
    };
    if (reducedMotion) {
      // Explicit reduced-motion mode, not a fake substitute for a missing engine.
      onFrame(parseCanvas(text, width, height));
      run.timeout = schedule(stop, 2400);
      return;
    }
    const args = [
      "--frame-rate", "120", "--canvas-width", String(width), "--canvas-height", String(height),
      "--ignore-terminal-dimensions", "--reuse-canvas", "--anchor-canvas", "c", "--anchor-text", "c",
      "--no-eol", "--no-restore-cursor", "laseretch",
    ];
    try {
      run.child = spawnProcess(executable, args, { stdio: ["pipe", "pipe", "pipe"], shell: false });
    } catch (error) {
      fail(error);
      return;
    }
    let stderr = "";
    const decoder = createDecoder(width, height, (canvas) => {
      if (current === run) onFrame(canvas);
    });
    run.timeout = schedule(() => fail(new Error("ttfx intro exceeded 30 seconds")), MAX_DURATION_MS);
    run.child.stdout.setEncoding("utf8");
    run.child.stderr.setEncoding("utf8");
    run.child.stdout.on("data", (chunk) => {
      if (current !== run) return;
      try { decoder.push(chunk); } catch (error) { fail(error); }
    });
    run.child.stderr.on("data", (chunk) => { stderr = (stderr + chunk).slice(-1000); });
    run.child.stdout.on("error", fail);
    run.child.stderr.on("error", fail);
    run.child.on("error", (error) => fail(new Error(`Cannot run ttfx: ${error.message}`)));
    run.child.stdin.on("error", (error) => fail(error));
    run.child.on("close", (code) => {
      run.closed = true;
      if (run.kill !== undefined) cancel(run.kill);
      if (current !== run) return;
      cancel(run.timeout);
      if (code !== 0) {
        fail(new Error(`ttfx exited ${code}: ${stderr.replace(/[\x00-\x1f\x7f]/g, " ")}`));
        return;
      }
      try { decoder.finish(); } catch (error) { fail(error); return; }
      run.hold = schedule(stop, 700);
    });
    run.child.stdin.end(text + "\n");
  }

  return { start, stop };
}
