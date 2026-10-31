import assert from "node:assert/strict";
import { EventEmitter } from "node:events";
import { test } from "node:test";
import { artwork, LOGO, WORDMARK, canShowIntro, hasIntroRequest } from "../plugins/daydream-intro/artwork.js";
import { createExplosion } from "../plugins/daydream-intro/outro.js";
import { createDecoder, createPlayback, MAX_DURATION_MS, parseCanvas } from "../plugins/daydream-intro/ttfx.js";
import { effectThemeArgs, PALETTE } from "../plugins/daydream-intro/theme.js";
import { paintCanvas } from "../plugins/daydream-intro/text.js";

const MARKER = "\x1b8\x1b7\x1b[4A";
const PAYLOAD = "  \x1b[38;2;119;155;255m/\x1b[0m \n \x1b[38;2;255;230;128mD\x1b[0m  \n    \n    ";

test("native text receives explicit RGB chunks without white overrides or backgrounds", () => {
  const node = {};
  class StyledText { constructor(chunks) { this.chunks = chunks; } }
  const RGBA = { fromHex: (hex) => ({ hex }) };
  paintCanvas(node, [{ text: "DAY", color: "#ff2bd6" }, { text: "DREAM", color: "#00f5ff" }], StyledText, RGBA);
  assert.deepEqual(node.content.chunks.map((chunk) => chunk.fg.hex), ["#ff2bd6", "#00f5ff"]);
  assert.equal(node.content.chunks.map((chunk) => chunk.text).join(""), "DAYDREAM");
  assert.ok(node.content.chunks.every((chunk) => chunk.__isChunk && !("bg" in chunk)));
  paintCanvas(node, [], StyledText, RGBA);
  assert.deepEqual(node.content.chunks, []);
});

test("artwork fits its intended canvas without resizing glyphs", () => {
  assert.equal(artwork(80, 16), LOGO);
  assert.match(artwork(40, 12), /D A Y D R E A M/);
  assert.equal(artwork(20, 6), "DAYDREAM");
  assert.ok(LOGO.split("\n").every((line) => [...line].length <= 74));
  assert.ok(LOGO.split("\n").length <= 14);
  assert.equal(LOGO, WORDMARK);
  assert.match(WORDMARK, /[╗╝╔╚═║]/u);
  assert.doesNotMatch(WORDMARK, /[╱╲]/u);
  assert.deepEqual(WORDMARK.split("\n").map((line) => line.match(/^ */)[0].length), [0, 0, 0, 0, 0, 0]);
  assert.doesNotMatch(artwork(40, 12), /DREAM IT|GODOT|\/\//);
});

test("the wordmark breaks into bounded colored particles before disappearing", () => {
  const original = [{ text: " DAYDREAM\n DAYDREAM", color: "#00f5ff" }];
  const burst = createExplosion(original, 20, 8);
  assert.equal(burst(0), original);
  const middle = burst(0.3);
  const text = middle.map((span) => span.text).join("");
  assert.match(text, /[*·]/u);
  assert.doesNotMatch(text, /DAYDREAM/);
  assert.ok(text.split("\n").every((line) => [...line].length <= 20));
  assert.ok(middle.some((span) => span.color === "#00f5ff" && span.text.trim()));
  assert.deepEqual(burst(1), []);
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

test("background RGB and OSC controls cannot introduce a black rectangle or reset foreground", () => {
  const spans = parseCanvas("\x1b[38;2;0;245;255mA\x1b[48;2;0;0;0mB\x1b[49mC", 8, 4);
  assert.deepEqual(spans, [{ text: "ABC", color: "#00f5ff" }]);
  assert.ok(spans.every((span) => !Object.keys(span).some((key) => /background|bg/i.test(key))));
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

test("playback keeps the real laser engine/timing and applies foreground-only cyberpunk colors", () => {
  const state = fixture();
  state.playback.start({ text: "DAYDREAM", width: 30, height: 10 });
  const [executable, args, options] = state.invocations[0];
  assert.equal(executable, "ttfx");
  assert.ok(args.includes("laseretch"));
  assert.deepEqual(args.slice(0, 2), ["--frame-rate", "120"]);
  assert.deepEqual(args.slice(args.indexOf("laseretch") + 1), effectThemeArgs());
  assert.equal(args.some((arg) => /background|etch-speed|etch-delay/.test(arg)), false);
  assert.equal(options.shell, false);
  assert.deepEqual(options.stdio, ["pipe", "pipe", "pipe"]);
  const child = state.children[0];
  assert.equal(child.input, "DAYDREAM\n");
  child.stdout.emit("data", MARKER + PAYLOAD);
  child.emit("close", 0);
  assert.equal(state.frames.length, 1);
  assert.equal(state.errors.length, 0);
  assert.equal(state.timers.size, 1);
  for (let i = 0; i < 25 && state.timers.size; i++) {
    const [id, timer] = [...state.timers][0];
    state.timers.delete(id);
    timer.callback();
  }
  assert.equal(state.hides, 1);
  assert.deepEqual(state.frames.at(-1), []);
});

test("reduced motion is static and never spawns a process", () => {
  const state = fixture();
  state.playback.start({ text: "DAYDREAM", width: 30, height: 10, reducedMotion: true });
  assert.equal(state.children.length, 0);
  assert.equal(state.frames[0].map((span) => span.text).join(""), "DAYDREAM");
  assert.equal(state.frames[0][0].color, "#" + PALETTE.final[0]);
  assert.equal(state.frames[0].at(-1).color, "#" + PALETTE.final.at(-1));
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
          assert.ok(frames.some((frame) => /DAYDREAM/.test(frame.map((span) => span.text).join(""))));
          const settled = frames.filter((frame) => /DAYDREAM/.test(frame.map((span) => span.text).join(""))).at(-1);
          assert.ok(new Set(settled.filter((span) => span.text.trim()).map((span) => span.color)).size >= 3);
          assert.deepEqual(frames.at(-1), []);
          resolve();
        } catch (error) { reject(error); }
      },
    });
    playback.start({ text: "DAYDREAM", width: 30, height: 10 });
  });
});
