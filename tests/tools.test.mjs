import { test } from 'node:test';
import assert from 'node:assert/strict';
import { definitions } from '../plugins/daydream-tools/adapter.js';
import { createRunner, resolveCheckout } from '../plugins/daydream-tools/runner.js';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { mkdtemp, mkdir, symlink, rm } from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';

const checkout = fileURLToPath(new URL('../', import.meta.url));
const run = createRunner(checkout, { python: 'python3' });
const catalog = await run(checkout, { action: 'catalog' });

test('installed directory symlink resolves the real checkout and executes catalog', async () => {
  const temporary = await mkdtemp(path.join(os.tmpdir(), 'daydream-plugin-'));
  try {
    const plugins = path.join(temporary, '.config', 'opencode', 'plugins');
    await mkdir(plugins, { recursive: true });
    const installed = path.join(plugins, 'daydream-tools');
    await symlink(path.join(checkout, 'plugins', 'daydream-tools'), installed, 'dir');
    const resolved = await resolveCheckout(pathToFileURL(path.join(installed, 'index.js')));
    assert.equal(resolved, path.resolve(checkout));
    const result = await createRunner(resolved, { python: 'python3' })(temporary, { action: 'catalog' });
    assert.equal(result.ok, true);
    assert.ok(result.result.operations.some(op => op.name === 'animation.assemble'));
  } finally { await rm(temporary, { recursive: true, force: true }); }
});

test('missing backend produces an actionable error without spawning Python', async () => {
  let spawned = false;
  const result = await createRunner(path.join(checkout, 'missing-checkout'), {}, () => { spawned = true; })(checkout, { action: 'catalog' });
  assert.equal(result.error.code, 'backend_missing');
  assert.equal(spawned, false);
});

test('native definitions derive exact canonical schemas and exclude approval', () => {
  assert.equal(catalog.ok, true);
  const tools = definitions({}, catalog, run);
  for (const op of catalog.result.operations.filter(op => op.tool)) {
    assert.deepEqual(tools.find(tool => tool.name === op.tool).input, op.input);
  }
  assert.equal(tools.some(tool => tool.name.includes('approve')), false);
});

test('permission denial stops before reading or writing and uses session location', async () => {
  const calls = [];
  const ctx = { session: { get: async () => ({ location: { directory: '/active/project' } }) },
    permission: { assert: async () => { throw new Error('denied'); } } };
  const backend = async (project, request) => {
    calls.push([project, request.action]);
    return { ok: true, access: { reads: ['/active/project/source.json'], writes: [] } };
  };
  const tool = definitions(ctx, catalog, backend).find(tool => tool.name === 'daydream_sprite_inspect');
  await assert.rejects(tool.execute({ bundle: 'art/dot' }, { sessionID: 'test' }), /denied/);
  assert.deepEqual(calls, [['/active/project', 'prepare']]);
});

test('apply authorizes preview outputs and forwards grants', async () => {
  const calls = [], permissions = [];
  const ctx = { session: { get: async () => ({ location: { directory: checkout } }) },
    permission: { assert: async request => { permissions.push(request.action); } } };
  const backend = async (_, request) => {
    calls.push(request);
    return { ok: true, status: 'preview', access: { reads: ['source'], writes: ['output'] } };
  };
  const tool = definitions(ctx, catalog, backend).find(tool => tool.name === 'daydream_sprite_edit');
  await tool.execute({ apply: true }, { sessionID: 'test' });
  assert.deepEqual(permissions, ['read', 'edit']);
  assert.equal(calls[1].input.apply, false);
  assert.deepEqual(calls[2].authorized, { reads: ['source'], writes: ['output'] });
});

test('already cancelled runner does not launch backend', async () => {
  const controller = new AbortController();
  controller.abort();
  const result = await run(checkout, { action: 'catalog' }, controller.signal);
  assert.equal(result.error.code, 'cancelled');
});
