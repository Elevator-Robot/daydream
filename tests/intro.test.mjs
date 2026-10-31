import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { test } from "node:test";
import { artwork, LOGO, canShowIntro, hasIntroRequest } from "../plugins/daydream-intro/artwork.js";
import { createDecoder, createPlayback, MAX_DURATION_MS, parseCanvas } from "../plugins/daydream-intro/ttfx.js";

const MARKER = "\x1b8\x1b7\x1b[4A";
const PAYLOAD = "  \x1b[38;2;119;155;255m/\x1b[0m \n \x1b[38;2;255;230;128mD\x1b[0m  \n    \n    ";

test("artwork fits its intended canvas without resizing glyphs", () => {
  assert.equal(artwork(80, 16), LOGO);
  assert.equal(artwork(40, 12), "DAYDREAM");
  assert.ok(LOGO.split("\n").every((line) => [...line].length <= 70));
});

test("the adapter preserves ttfx's actual character positions and RGB colors", () => {
  const spans = parseCanvas(PAYLOAD, 4, 4);
  assert.equal(spans.map((span) => span.text).join(""), "  / \n D  \n    \n    ");
  assert.ok(spans.some((span) => span.text === "/" && span.color === "#779bff"));
  assert.ok(spans.some((span) => span.text === "D" && span.color === "#ffe680"));
  assert.doesNotMatch(spans.map((span) => span.text).join(""), /\x1b/);
});

test("frame decoder handles arbitrarily split markers and keeps the final frame", () => {
  const frames = [];
  const decoder = createDecoder(4, 4, (canvas) => frames.push(canvas));
  const output = "\x1b[?25l" + MARKER + PAYLOAD + MARKER + "DONE";
  for (const character of output) decoder.push(character);
  assert.equal(frames.length, 1);
  decoder.finish();
  assert.equal(frames.length, 2);
  assert.equal(frames[1].map((span) => span.text).join(""), "DONE");
});

test("parser bounds the canvas and drops terminal operations", () => {
  const spans = parseCanvas("\x1b[?25l\x1b]11;rgb:00/00/00\x07ABCDE\nFGHIJ\nK", 4, 2);
  assert.equal(spans.map((span) => span.text).join(""), "ABCD\nFGHI");
  assert.throws(() => createDecoder(4, 4, () => {}).finish(), /no supported canvas/);
  assert.throws(() => createDecoder(4, 4, () => {}).push("x".repeat(1024 * 1024 + 1)), /safety limit/);
});

test("only a visible primary Daydream session is eligible to show requested art", () => {
  const session = { id: "one", agent: "daydream" };
  const route = { type: "session", sessionID: "one" };
  assert.equal(canShowIntro(session, route), true);
  for (const candidate of [undefined, { ...session, agent: "build" }, { ...session, parentID: "parent" }]) {
    assert.equal(canShowIntro(candidate, route), false);
  }
  assert.equal(canShowIntro(session, { type: "home" }), false);
  assert.equal(canShowIntro(session, { type: "session", sessionID: "other" }), false);
});

test("/agent selection and session restoration without an explicit request never play art", () => {
  assert.equal(hasIntroRequest("one", undefined, undefined), false);
  const request = { sessionID: "one" };
  assert.equal(hasIntroRequest("one", request, undefined), true);
  assert.equal(hasIntroRequest("other", request, undefined), false);
  assert.equal(hasIntroRequest("one", request, request), false);
  // An explicit replay is a new request, even for the same session.
  assert.equal(hasIntroRequest("one", { sessionID: "one" }, request), true);
});

function fixture() {
  const frames = [];
  const errors = [];
  const timers = new Map();
  const children = [];
  const invocations = [];
  let hides = 0;
  let next = 0;
  const playback = createPlayback({
    onFrame: (value) => frames.push(value), onHide: () => hides++, onError: (error) => errors.push(error),
    schedule: (callback, delay) => { timers.set(++next, { callback, delay }); return next; },
    cancel: (id) => timers.delete(id),
    spawnProcess: (...args) => {
      invocations.push(args);
      const child = new EventEmitter();
      child.stdout = new EventEmitter();
      child.stderr = new EventEmitter();
      child.stdin = new EventEmitter();
      child.stdout.setEncoding = child.stderr.setEncoding = () => {};
      child.stdin.end = (text) => { child.input = text; };
      child.signals = [];
      child.kill = (signal) => child.signals.push(signal);
      children.push(child);
      return child;
    },
  });
  return { playback, frames, errors, timers, children, invocations, get hides() { return hides; } };
}

test("playback invokes the real engine with Omarchy timing/default laser settings", () => {
  const state = fixture();
  state.playback.start({ text: "DAYDREAM", width: 30, height: 10 });
  const [executable, args, options] = state.invocations[0];
  assert.equal(executable, "ttfx");
  assert.equal(args.at(-1), "laseretch");
  assert.deepEqual(args.slice(0, 2), ["--frame-rate", "120"]);
  assert.equal(args.some((arg) => /gradient|etch-speed|etch-delay/.test(arg)), false);
  assert.equal(options.shell, false);
  assert.deepEqual(options.stdio, ["pipe", "pipe", "pipe"]);
  const child = state.children[0];
  assert.equal(child.input, "DAYDREAM\n");
  child.stdout.emit("data", MARKER + PAYLOAD);
  child.emit("close", 0);
  assert.equal(state.frames.length, 1);
  assert.equal(state.errors.length, 0);
  assert.equal(state.timers.size, 1);
  [...state.timers.values()][0].callback();
  assert.equal(state.hides, 1);
});

test("reduced motion is static and never spawns a process", () => {
  const state = fixture();
  state.playback.start({ text: "DAYDREAM", width: 30, height: 10, reducedMotion: true });
  assert.equal(state.children.length, 0);
  assert.equal(state.frames[0].map((span) => span.text).join(""), "DAYDREAM");
  state.playback.stop();
  assert.equal(state.timers.size, 0);
});

test("cancellation kills only its owned process and ignores stale output", () => {
  const state = fixture();
  state.playback.start({ text: "DAYDREAM", width: 30, height: 10 });
  const child = state.children[0];
  state.playback.stop();
  assert.deepEqual(child.signals, ["SIGTERM"]);
  child.stdout.emit("data", MARKER + PAYLOAD + MARKER);
  assert.equal(state.frames.length, 0);
  [...state.timers.values()][0].callback();
  assert.deepEqual(child.signals, ["SIGTERM", "SIGKILL"]);
  child.emit("close", null);
  assert.equal(state.timers.size, 0);
});

test("missing engine, timeouts, and invalid canvases fail without an imitation fallback", () => {
  for (const reason of ["missing", "timeout"]) {
    const state = fixture();
    state.playback.start({ text: "DAYDREAM", width: 30, height: 10 });
    if (reason === "missing") state.children[0].emit("error", new Error("ENOENT"));
    else [...state.timers.values()].find((timer) => timer.delay === MAX_DURATION_MS).callback();
    assert.equal(state.errors.length, 1);
    assert.equal(state.frames.length, 0);
    state.children[0].emit("close", 1);
    assert.equal(state.timers.size, 0);
  }
  const state = fixture();
  state.playback.start({ text: "x", width: -1, height: 10 });
  assert.equal(state.errors.length, 1);
  assert.equal(state.children.length, 0);
});

test("real ttfx laseretch output decodes with its original colors", {
  skip: !process.env.TTFX_BIN,
  timeout: 20000,
}, async () => {
  await new Promise((resolve, reject) => {
    const frames = [];
    const playback = createPlayback({
      executable: process.env.TTFX_BIN,
      onFrame: (frame) => frames.push(frame),
      onError: reject,
      onHide: () => {
        try {
          assert.ok(frames.length > 10);
          assert.ok(frames.some((frame) => frame.some((span) => span.color !== "#ffffff")));
          assert.match(frames.at(-1).map((span) => span.text).join(""), /DAYDREAM/);
          resolve();
        } catch (error) { reject(error); }
      },
    });
    playback.start({ text: "DAYDREAM", width: 30, height: 10 });
  });
});
