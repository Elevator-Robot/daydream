import { Plugin } from "@opencode/plugin";
import { createRunner, resolveCheckout } from "./runner.js";
import { definitions } from "./adapter.js";
import { createPreviewService, PreviewFailure } from "./preview.js";
import { Preview } from "./rpc.js";
import { previewInput } from "./preview-contract.js";
import { createReviewService } from "./review.js";
import { Review } from "./review-rpc.js";

export default Plugin.define({
  id: "daydream.tools",
  async setup(ctx) {
    if (ctx.options.enabled === false) return;
    const checkout = await resolveCheckout(import.meta.url);
    const active = new Set();
    let closed = false;
    const bind = backend => async (project, request, signal) => {
      const controller = new AbortController();
      const abort = () => controller.abort();
      if (closed || signal?.aborted) controller.abort();
      signal?.addEventListener("abort", abort, { once: true });
      active.add(controller);
      try { return await backend(project, request, controller.signal); }
      finally { active.delete(controller); signal?.removeEventListener("abort", abort); }
    };
    const run = bind(createRunner(checkout, ctx.options));
    const runReview = bind(createRunner(checkout, ctx.options, undefined, 'review_ui'));
    const catalog = await run(ctx.location.directory, { action: "catalog" });
    if (!catalog.ok) throw new Error(catalog.error.message);
    const tools = definitions(ctx, catalog, run);
    const previews = createPreviewService(ctx, run);
    const reviews = createReviewService(ctx, runReview, previews);
    const reviewRPC = await ctx.rpc.register(Review, {
      call: async (input, context) => {
        try { return await reviews.call(input, { signal: context.signal }); }
        catch (error) {
          if (error instanceof PreviewFailure || error instanceof SyntaxError || ['ENOENT', 'EACCES', 'ELOOP'].includes(error.code)) {
            return context.error('review_failed', error.message, {});
          }
          throw error;
        }
      },
    });
    const rpc = await ctx.rpc.register(Preview, {
      call: async (input, context) => {
        try { return await previews.call(input, { signal: context.signal }); }
        catch (error) {
          if (error instanceof PreviewFailure || error instanceof SyntaxError || ['ENOENT', 'EACCES', 'ELOOP'].includes(error.code)) {
            return context.error('preview_failed', error.message, {});
          }
          // Let permission rejection/interruption retain OpenCode semantics.
          throw error;
        }
      },
    });
    tools.push({
      name: 'daydream_preview',
      description: 'Launch, inspect, or stop the active project graphical Godot preview, or list sprite/animation/tileset revisions. Only stops the game this plugin launched. Launch runs project code and requires permissions. Users can also run /preview directly in the TUI without a model call. Preview never approves artwork.',
      input: { type: 'object', properties: { action: { ...previewInput.properties.action, enum: ['game', 'status', 'stop', 'assets'] }, scene: previewInput.properties.scene }, required: ['action'], additionalProperties: false },
      options: { codemode: true },
      execute: async (input, context) => ({ content: JSON.stringify(await previews.call({ ...input, sessionID: context.sessionID }, {
        signal: context.signal, source: { type: 'tool', messageID: context.messageID, id: context.id },
      })) }),
    });
    const registration = await ctx.tool.transform((editor) => { for (const tool of tools) editor.add(tool); });
    return async () => {
      closed = true;
      reviews.dispose();
      for (const controller of active) controller.abort();
      await previews.dispose();
      await rpc.dispose();
      await reviewRPC.dispose();
      await registration.dispose();
    };
  },
});
