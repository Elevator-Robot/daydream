import { errorResult } from "./runner.js";

// Registration is derived from the Python catalog, never a second operation map.
export function definitions(ctx, catalog, run) {
  const operations = catalog.result.operations;
  const byName = new Map(operations.map((operation) => [operation.name, operation]));
  const content = (value) => ({ content: JSON.stringify(value) });
  async function workspace(execution) {
    const session = await ctx.session.get({ sessionID: execution.sessionID });
    return session.location.directory;
  }
  async function assert(execution, action, resources) {
    if (!resources.length) return;
    await ctx.permission.assert({ sessionID: execution.sessionID, agent: execution.agent,
      source: { type: "tool", messageID: execution.messageID, id: execution.id }, action,
      resources, save: resources,
    });
  }
  async function call(name, input, execution) {
    const operation = byName.get(name);
    if (!operation?.native) return content(errorResult("unsupported", "Operation is not exposed as a native tool; approvals require explicit human-reviewed CLI workflow"));
    const project = await workspace(execution);
    const prepared = await run(project, { action: "prepare", op: name, input }, execution.signal);
    if (!prepared.ok) return content(prepared);
    // Permission failures propagate. No CLI fallback or allow-rule mutation.
    await assert(execution, "read", prepared.access.reads);
    const previewInput = operation.effect === "read" ? input : { ...input, apply: false };
    const authorized = { reads: prepared.access.reads, writes: [] };
    const preview = await run(project, { action: "call", op: name, input: previewInput, authorized }, execution.signal);
    if (!preview.ok || operation.effect === "read" || input.apply !== true) return content(preview);
    await assert(execution, "edit", preview.access.writes);
    return content(await run(project, { action: "call", op: name, input, authorized: { ...authorized, writes: preview.access.writes } }, execution.signal));
  }
  const tools = [
    {
      name: "daydream_search", description: "Discover existing Daydream sprite/animation/tileset/project operations by goal. Returns exact schemas and native/CLI availability; does not search files or run Summer.",
      input: { type: "object", properties: { query: { type: "string", maxLength: 500 }, limit: { type: "integer", minimum: 1, maximum: 50 } }, additionalProperties: false },
      options: { codemode: true },
      execute: async (input, execution) => content(await run(await workspace(execution), { action: "search", query: input.query ?? "", limit: input.limit ?? 10 }, execution.signal)),
    },
    {
      name: "daydream_describe", description: "Read the canonical input contract, effect, and native availability of one Daydream operation before calling it.",
      input: { type: "object", properties: { op: { type: "string", maxLength: 80 } }, required: ["op"], additionalProperties: false },
      options: { codemode: true },
      execute: async (input, execution) => content(await run(await workspace(execution), { action: "describe", op: input.op }, execution.signal)),
    },
    {
      name: "daydream_call", description: "Run a discovered Daydream operation against the active session's project. Writes preview by default; apply:true requests permissioned writes, never artwork approval. No arbitrary scripts, shell flags, installs, engine launch, or cloud providers.",
      input: { type: "object", properties: { op: { type: "string", enum: operations.filter((operation) => operation.native).map((operation) => operation.name) }, input: { type: "object" } }, required: ["op", "input"], additionalProperties: false },
      options: { codemode: true }, execute: (input, execution) => call(input.op, input.input, execution),
    },
  ];
  for (const operation of operations) {
    if (!operation.native || !operation.tool) continue;
    tools.push({ name: operation.tool,
      description: `${operation.summary}. Uses the active project only. Write actions preview unless apply:true; approval remains a separate human review. Preview paths are not proof the images/motion were viewed.`,
      input: operation.input, options: { codemode: true }, execute: (input, execution) => call(operation.name, input, execution) });
  }
  return tools;
}
