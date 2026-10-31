import assert from "node:assert/strict";
import { test } from "node:test";
import { createPlayback, DURATION_MS, frame, LOGO, shouldStart, TAGLINE } from "../plugins/daydream-intro/animation.js";

test("laser etches the wordmark and never emits terminal control sequences", () => {
  const final = frame(1);
  assert.ok(final.includes(LOGO.join("\n")));
  assert.ok(final.includes(TAGLINE));
  assert.notEqual(frame(0), final);
  assert.match(frame(0.5), /[┃╋]/u);
  assert.doesNotMatch(final, /[┃╋]/u);
  for (let i = 0; i <= 20; i++) assert.doesNotMatch(frame(i / 20), /[\x00-\x09\x0b-\x1f\x7f]/);
});

test("small terminals use a bounded compact logo", () => {
  for (const width of [0, 1, 12, 30, 54, 55, 80]) {
    for (const height of [0, 1, 3, 12, 24]) {
      const output = frame(1, width, height);
      assert.ok(output === "" || output.split("\n").length <= height);
      assert.ok(output.split("\n").every((line) => [...line].length <= width));
    }
  }
  assert.ok(frame(1, 40).includes("DAYDREAM"));
});

test("only the visible primary Daydream session starts automatically", () => {
  const session = { id: "one", agent: "daydream" };
  const route = { type: "session", sessionID: "one" };
  assert.equal(shouldStart(session, route, []), true);
  for (const candidate of [undefined, { ...session, agent: "build" }, { ...session, parentID: "parent" }]) {
    assert.equal(shouldStart(candidate, route, []), false);
  }
  assert.equal(shouldStart(session, { type: "home" }, []), false);
  assert.equal(shouldStart(session, { type: "session", sessionID: "other" }, []), false);
  assert.equal(shouldStart(session, route, ["one"]), false);
});

function clock() {
  let time = 0;
  let next = 0;
  const pending = new Map();
  const frames = [];
  let hidden = 0;
  const playback = createPlayback({
    onFrame: (value) => frames.push(value),
    onHide: () => hidden++,
    now: () => time,
    schedule: (callback, delay) => {
      const id = ++next;
      pending.set(id, { callback, due: time + delay });
      return id;
    },
    cancel: (id) => pending.delete(id),
  });
  return {
    playback, frames, pending,
    get hidden() { return hidden; },
    advance(value) {
      const end = time + value;
      while (pending.size) {
        const [id, job] = [...pending].sort((a, b) => a[1].due - b[1].due)[0];
        if (job.due > end) break;
        pending.delete(id);
        time = job.due;
        job.callback();
      }
      time = end;
    },
  };
}

test("animation is bounded, settles, and stops all scheduled work", () => {
  const state = clock();
  state.playback.start();
  state.advance(DURATION_MS);
  assert.equal(state.frames[0], 0);
  assert.equal(state.frames.at(-1), 1);
  assert.equal(state.hidden, 1);
  assert.equal(state.pending.size, 0);
  assert.ok(state.frames.length <= 50);
});

test("reduced motion shows one static frame with no animation loop", () => {
  const state = clock();
  state.playback.start({ reducedMotion: true });
  state.advance(DURATION_MS);
  assert.deepEqual(state.frames, [1]);
  assert.equal(state.hidden, 1);
  assert.equal(state.pending.size, 0);
});

test("dismissal, unmount, and restart cancel stale callbacks", () => {
  const state = clock();
  state.playback.start();
  const stale = [...state.pending.values()][0].callback;
  state.playback.stop();
  assert.equal(state.pending.size, 0);
  state.playback.start({ reducedMotion: true });
  const count = state.frames.length;
  stale();
  assert.equal(state.frames.length, count);
  state.playback.stop();
  state.playback.stop();
  assert.equal(state.hidden, 2);
  assert.equal(state.pending.size, 0);
});
