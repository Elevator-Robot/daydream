import { realpath } from 'node:fs/promises';
import { PreviewFailure } from './preview.js';

export function createDashboardService(ctx, run) {
  let closed = false;
  return {
    async call(input, { signal } = {}) {
      if (closed || signal?.aborted) throw new PreviewFailure('Dashboard disconnected');
      if (!['catalog', 'inspect', 'media'].includes(input.action)) throw new PreviewFailure('Unknown dashboard action');
      const session = await ctx.session.get({ sessionID: input.sessionID });
      const root = await realpath(session.location.directory);
      if (root !== await realpath(ctx.location.directory) || root !== await realpath(input.project)) throw new PreviewFailure('This session moved projects. Reopen the dashboard from the intended project.');
      const op = 'dashboard.' + input.action;
      const data = input.action === 'catalog' ? {} : {
        path: input.path, kind: input.kind,
        ...(input.revision_hash ? { revision_hash: input.revision_hash } : {}),
        ...(input.action === 'media' ? { image: input.image ?? 'thumbnail' } : {}),
      };
      const check = value => { if (!value.ok) throw new PreviewFailure(value.error?.message ?? 'Dashboard read failed'); return value; };
      const prepared = check(await run(root, { action: 'prepare', op, input: data }, signal));
      const authorized = { reads: prepared.access.reads, writes: [] };
      if (authorized.reads.length) await ctx.permission.assert({ sessionID: input.sessionID, action: 'read', resources: authorized.reads, save: authorized.reads });
      if (prepared.access.read_resolution) {
        const resolved = check(await run(root, { action: 'resolve', op, input: data, authorized }, signal));
        const extra = resolved.access.reads.filter(file => !authorized.reads.includes(file));
        if (extra.length) await ctx.permission.assert({ sessionID: input.sessionID, action: 'read', resources: extra, save: extra });
        authorized.reads = resolved.access.reads;
      }
      if (closed || signal?.aborted) throw new PreviewFailure('Dashboard read cancelled');
      return { ok: true, ...check(await run(root, { action: 'call', op, input: data, authorized }, signal)).result };
    },
    dispose() { closed = true; },
  };
}
