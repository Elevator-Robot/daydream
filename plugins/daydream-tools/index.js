import { Plugin } from "@opencode/plugin";
import { createRunner, resolveCheckout } from "./runner.js";
import { definitions } from "./adapter.js";

export default Plugin.define({
  id: "daydream.tools",
  async setup(ctx) {
    if (ctx.options.enabled === false) return;
    const checkout = await resolveCheckout(import.meta.url);
    const backend = createRunner(checkout, ctx.options);
    const active = new Set();
    let closed = false;
    const run = async (project, request, signal) => {
      const controller = new AbortController();
      const abort = () => controller.abort();
      if (closed || signal?.aborted) controller.abort();
      signal?.addEventListener("abort", abort, { once: true });
      active.add(controller);
      try { return await backend(project, request, controller.signal); }
      finally { active.delete(controller); signal?.removeEventListener("abort", abort); }
    };
    const catalog = await run(ctx.location.directory, { action: "catalog" });
    if (!catalog.ok) throw new Error(catalog.error.message);
    const tools = definitions(ctx, catalog, run);
    const registration = await ctx.tool.transform((editor) => { for (const tool of tools) editor.add(tool); });
    return async () => {
      closed = true;
      for (const controller of active) controller.abort();
      await registration.dispose();
    };
  },
});
