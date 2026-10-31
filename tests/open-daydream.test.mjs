import assert from "node:assert/strict";
import { test } from "node:test";
import { createOpenDaydream } from "../plugins/daydream-intro/open.js";
import { commandLayer } from "../plugins/daydream-intro/commands.js";
import { launcherRequest } from "../plugins/daydream-intro/launch.js";

test("terminal startup is one-shot and cannot trigger for an ordinary /agent entry", () => {
  const session = { id: "ses_launch", agent: "daydream" };
  const route = { type: "session", sessionID: session.id };
  assert.deepEqual(launcherRequest(session.id, session, route, []), { sessionID: session.id });
  assert.equal(launcherRequest(undefined, session, route, []), undefined);
  assert.equal(launcherRequest(session.id, session, route, [session.id]), undefined);
  assert.equal(launcherRequest("ses_other", session, route, []), undefined);
  assert.equal(launcherRequest(session.id, { ...session, parentID: "parent" }, route, []), undefined);
  assert.equal(launcherRequest(session.id, { ...session, agent: "build" }, route, []), undefined);
  assert.equal(launcherRequest(session.id, session, { type: "home" }, []), undefined);
});

function fixture() {
  const calls = [];
  const agents = [{ id: "daydream", mode: "all", hidden: false }];
  const location = { directory: "/games/my game" };
  const context = {
    location,
    client: {
      session: {
        create: async (input) => { calls.push(["create", input]); return { id: "new-session", agent: "daydream" }; },
        prompt: () => { throw new Error("Never submit a prompt"); },
        generate: () => { throw new Error("Never call a model"); },
      },
    },
    data: {
      location: {
        default: () => ({ directory: "/fallback" }),
        agent: {
          sync: async (location) => calls.push(["agents", location]),
          list: () => agents,
        },
      },
      session: { sync: async (id) => calls.push(["sync", id]) },
    },
    ui: {
      model: { current: () => ({ providerID: "chosen", modelID: "existing-model", variant: "existing-variant" }) },
      router: { navigate: (route) => calls.push(["navigate", route]) },
      toast: { show: (toast) => calls.push(["error", toast]) },
    },
  };
  const busy = [];
  const requested = [];
  const open = createOpenDaydream(context, (value) => busy.push(value), (id) => {
    assert.equal(calls.at(-1)[0], "navigate");
    requested.push(id);
  });
  return { context, calls, agents, busy, requested, open };
}

test("home-screen entry is a global palette action, not a base-mode-only command", async () => {
  const state = fixture();
  let busy = false;
  const layer = commandLayer(state.context, {
    opening: () => busy, openDaydream: state.open, setReplay: () => {}, setDismissal: () => {},
  });
  assert.equal(layer.mode, "global");
  const entry = layer.commands.find((command) => command.id === "daydream.open");
  assert.equal(entry.title, "Open Daydream");
  assert.equal(entry.palette, true);
  assert.equal(entry.slash.name, "daydream");
  assert.equal(entry.enabled(), true);
  busy = true;
  assert.equal(entry.enabled(), false);
  busy = false;
  await entry.run();
  assert.equal(state.calls.at(-1)[0], "navigate");
});

test("Open Daydream creates and opens an empty selected-agent session before any prompt", async () => {
  const state = fixture();
  assert.equal(await state.open(), "new-session");
  assert.deepEqual(state.calls.map(([name]) => name), ["agents", "create", "sync", "navigate"]);
  assert.deepEqual(state.calls[1][1], {
    title: "Daydream", agent: "daydream", location: { directory: "/games/my game" },
    model: { providerID: "chosen", id: "existing-model", variant: "existing-variant" },
  });
  assert.deepEqual(state.calls.at(-1)[1], { type: "session", sessionID: "new-session" });
  assert.deepEqual(state.busy, [true, false]);
  assert.deepEqual(state.requested, ["new-session"]);
});

test("does not choose a model when none is selected and uses the current default location", async () => {
  const state = fixture();
  state.context.location = undefined;
  state.context.ui.model.current = () => undefined;
  await state.open();
  const input = state.calls.find(([name]) => name === "create")[1];
  assert.equal("model" in input, false);
  assert.deepEqual(input.location, { directory: "/fallback" });
});

test("missing, hidden, or subagent-only definitions do not create a fallback Build session", async () => {
  for (const agent of [undefined, { id: "daydream", mode: "subagent" }, { id: "daydream", mode: "all", hidden: true }]) {
    const state = fixture();
    state.agents.splice(0, 1, ...(agent ? [agent] : []));
    await state.open();
    assert.equal(state.calls.some(([name]) => name === "create"), false);
    assert.equal(state.calls.at(-1)[0], "error");
    assert.deepEqual(state.busy, [true, false]);
    assert.deepEqual(state.requested, []);
  }
});

test("double activation creates only one session", async () => {
  const state = fixture();
  await Promise.all([state.open(), state.open()]);
  assert.equal(state.calls.filter(([name]) => name === "create").length, 1);
});

test("failed session creation surfaces an error without navigating", async () => {
  const state = fixture();
  state.context.client.session.create = async () => { throw new Error("Cannot create session"); };
  await state.open();
  assert.equal(state.calls.at(-1)[1].message, "Cannot create session");
  assert.equal(state.calls.some(([name]) => name === "navigate"), false);
  assert.deepEqual(state.requested, []);
  assert.deepEqual(state.busy, [true, false]);
});

test("failed sync retries the same empty session without duplicate creation or deletion", async () => {
  const state = fixture();
  let attempts = 0;
  state.context.data.session.sync = async (id) => {
    if (++attempts === 1) throw new Error("Sync unavailable");
    state.calls.push(["sync", id]);
  };
  await state.open();
  assert.equal(await state.open(), "new-session");
  assert.equal(state.calls.filter(([name]) => name === "create").length, 1);
  assert.equal(state.calls.at(-1)[0], "navigate");
});
