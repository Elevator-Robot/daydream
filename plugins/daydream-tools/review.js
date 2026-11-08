import { randomUUID } from 'node:crypto';
import { realpath } from 'node:fs/promises';
import { PreviewFailure, projectPath } from './preview.js';

const fail = message => { throw new PreviewFailure(message); };

// User-interface service only: never registered as a model-facing decision tool.
// This is a workflow boundary, not authentication against arbitrary local code.
export function createReviewService(ctx, run, previews, now = Date.now) {
  const tickets = new Map();
  let disposed = false;
  async function workspace(sessionID) {
    const session = await ctx.session.get({ sessionID });
    const root = await realpath(session.location.directory);
    if (root !== await realpath(ctx.location.directory)) fail('Review belongs to a different plugin location');
    return root;
  }
  async function operation(root, sessionID, op, input, signal, apply = false) {
    if (disposed || signal?.aborted) fail('Review cancelled');
    const check = result => {
      if (!result.ok) fail((result.error?.message ?? 'Review operation failed') + (result.error?.partial_possible
        ? '\nNew output may be partial. Inspect it before retrying; no automatic rollback was performed.' : ''));
      return result;
    };
    const prepared = check(await run(root, { action: 'prepare', op, input }, signal));
    if (prepared.access.reads.length) await ctx.permission.assert({ sessionID, action: 'read', resources: prepared.access.reads, save: prepared.access.reads });
    const authorized = { reads: prepared.access.reads, writes: [] };
    if (prepared.access.engine_resolution || prepared.access.read_resolution) {
      const resolved = check(await run(root, { action: 'resolve', op, input, authorized }, signal));
      const extra = resolved.access.reads.filter(file => !authorized.reads.includes(file));
      if (extra.length) await ctx.permission.assert({ sessionID, action: 'read', resources: extra, save: extra });
      authorized.reads = resolved.access.reads;
      if (resolved.access.executables?.length) {
        await ctx.permission.assert({ sessionID, action: 'daydream.engine.serialize', resources: [root, ...resolved.access.executables], save: [] });
        authorized.executables = resolved.access.executables;
      }
    }
    const isRead = prepared.effect === 'read';
    const preview = check(await run(root, { action: 'call', op, input: isRead ? input : { ...input, apply: false }, authorized }, signal));
    if (!apply || isRead) return preview;
    if (input.strategy === 'update') {
      await ctx.permission.assert({ sessionID, action: 'daydream.asset.update', resources: [root, input.target, preview.result.plan_hash], save: [] });
    }
    if (preview.access.writes.length) await ctx.permission.assert({ sessionID, action: 'edit', resources: preview.access.writes, save: preview.access.writes });
    if (disposed || signal?.aborted) fail('Review cancelled before writing');
    return check(await run(root, { action: 'call', op, input: { ...input, apply: true }, authorized: { ...authorized, writes: preview.access.writes } }, signal));
  }
  async function inspect(ticket, signal) {
    const result = await operation(ticket.root, ticket.sessionID, 'review.inspect', { bundle: ticket.bundle, kind: ticket.kind }, signal);
    if (result.result.revision_hash !== ticket.hash) fail('Revision changed after preview. Open a fresh review; no decision was written');
    return result.result;
  }
  return {
    async call(input, { signal } = {}) {
      if (disposed || signal?.aborted) fail('Review cancelled');
      const root = await workspace(input.sessionID);
      for (const [id, ticket] of tickets) if (ticket.expires <= now() && !ticket.busy) tickets.delete(id);
      if (input.action === 'open') {
        if (tickets.size >= 64) fail('Too many open reviews; cancel an older review first');
        const bundle = await projectPath(root, input.bundle);
        const document = await previews.call({ sessionID: input.sessionID, action: 'asset', bundle }, { signal });
        const ticket = { root, sessionID: input.sessionID, bundle, kind: document.kind, hash: document.revision_hash, expires: now() + 20 * 60 * 1000, busy: false };
        const status = await inspect(ticket, signal);
        if (disposed || signal?.aborted) fail('Review cancelled');
        const id = randomUUID();
        tickets.set(id, ticket);
        return { ...document, ticket: id, bundle, status, expires_at: ticket.expires };
      }
      const ticket = tickets.get(input.ticket);
      if (!ticket || ticket.root !== root || ticket.sessionID !== input.sessionID || ticket.expires <= now()) fail('Review expired or does not belong to this session; open it again');
      if (input.action === 'cancel') {
        if (ticket.busy) fail('Review action is in progress');
        tickets.delete(input.ticket);
        return { ok: true, state: 'cancelled' };
      }
      if (ticket.busy) fail('A decision or import is already in progress for this review');
      ticket.busy = true;
      try {
        const status = await inspect(ticket, signal);
        if (input.action === 'options') {
          const result = await operation(root, input.sessionID, 'assets.options', { kind: ticket.kind, bundle: ticket.bundle }, signal);
          return { ok: true, ...result.result };
        }
        if (input.action === 'setup') {
          const result = await operation(root, input.sessionID, 'project.init', {}, signal, true);
          return { ok: true, result: result.result };
        }
        if (input.action === 'approve' || input.action === 'changes') {
          await ctx.permission.assert({ sessionID: input.sessionID, action: 'daydream.review.' + input.action,
            resources: [ticket.bundle + '#' + ticket.hash], save: [],
            metadata: { kind: ticket.kind, revision_hash: ticket.hash, reviewer: input.reviewer, decision: input.action } });
          const data = { bundle: ticket.bundle, revision_hash: ticket.hash, reviewer: input.reviewer };
          const result = input.action === 'approve'
            ? await operation(root, input.sessionID, ticket.kind + '.approve', data, signal, true)
            : await operation(root, input.sessionID, 'review.feedback', { ...data, kind: ticket.kind, feedback: input.feedback }, signal, true);
          ticket.plan = undefined;
          return { ok: true, result: result.result, status: await inspect(ticket, signal) };
        }
        if (input.action === 'plan') {
          if (status.state !== 'approved') fail('Only this exact approved revision can be planned for import');
          const data = { bundle: ticket.bundle, revision_hash: ticket.hash };
          data.strategy = input.strategy ?? 'copy';
          if (input.target) data.target = input.target;
          if (input.name) data.name = input.name;
          if (input.destination) data.destination = input.destination;
          let op = ticket.kind + '.import';
          if (input.layout === 'editor') {
            if (ticket.kind !== 'tileset') fail('Editor cell serialization applies only to tilesets');
            op = 'tileset.editor_import';
            if (input.godot) data.godot = input.godot;
            if (input.godot_version) data.godot_version = input.godot_version;
          }
          const result = await operation(root, input.sessionID, op, data, signal);
          ticket.plan = { operation: op, input: data, hash: result.result.plan_hash };
          return { ok: true, plan: result.result };
        }
        if (input.action === 'import') {
          if (status.state !== 'approved' || !ticket.plan) fail('Approve the exact revision and review an import plan first');
          const result = await operation(root, input.sessionID, ticket.plan.operation, { ...ticket.plan.input, plan_hash: ticket.plan.hash }, signal, true);
          tickets.delete(input.ticket); // A successful import is never automatically retried.
          return { ok: true, state: 'imported', result: result.result };
        }
        fail('Unknown review action');
      } finally { ticket.busy = false; }
    },
    dispose() { disposed = true; tickets.clear(); },
  };
}
