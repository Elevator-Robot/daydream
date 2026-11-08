import { test } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createDashboardBridge, createDashboardManager } from '../plugins/daydream-tools/dashboard-bridge.js';
import { createDashboardService } from '../plugins/daydream-tools/dashboard-service.js';
import { createRunner } from '../plugins/daydream-tools/runner.js';
import { request } from 'node:http';
import { clampZoom, fitZoom, zoomAt, MIN_ZOOM, MAX_ZOOM } from '../dashboard/src/canvas-math.mjs';

const checkout = fileURLToPath(new URL('../', import.meta.url));
const python = process.env.DAYDREAM_TEST_PYTHON ?? 'python3';
const pillow = spawnSync(python, ['-c', 'import PIL']).status === 0;
const entry = { id: 'asset-key', kind: 'sprite', path: 'art/dot', revision_hash: 'a'.repeat(64) };

test('canvas fit uses crisp integer upscaling and bounded downscaling', () => {
  assert.equal(fitZoom(32, 32, 800, 500), 8);
  assert.equal(fitZoom(16, 16, 1200, 1000), 8);
  assert.ok(fitZoom(4096, 4096, 500, 500) < 1);
  assert.equal(clampZoom(1000), MAX_ZOOM);
  assert.equal(clampZoom(0), MIN_ZOOM);
});

test('canvas zoom keeps the pointed image pixel fixed, including after panning', () => {
  const before = { scale: 4, x: 30, y: -20 }, point = { x: 120, y: 70 };
  const after = zoomAt(before, 8, point);
  assert.equal((point.x - before.x) / before.scale, (point.x - after.x) / after.scale);
  assert.equal((point.y - before.y) / before.scale, (point.y - after.y) / after.scale);
  const restored = zoomAt(after, 4, point);
  assert.deepEqual(restored, before);
  assert.deepEqual(zoomAt({ scale: MAX_ZOOM, x: 0, y: 0 }, 100, point), { scale: MAX_ZOOM, x: 0, y: 0 });
});

async function fixture(t, handler) {
  const calls = [];
  const bridge = await createDashboardBridge({ sessionID: 'session', project: '/chosen/project', call: async (input, options) => {
    calls.push(input); return handler ? handler(input, options) : { ok: true, assets: [entry] };
  } });
  t.after(() => bridge.dispose());
  const url = new URL(bridge.url), origin = url.origin;
  const headers = { Authorization: 'Bearer ' + new URLSearchParams(url.hash.slice(1)).get('token') };
  return { bridge, calls, origin, headers, get: (route, options = {}) => fetch(origin + route, { headers, ...options }) };
}

test('dashboard serves bundled UI and requires its capability for all project data', async t => {
  const f = await fixture(t);
  const page = await fetch(f.origin);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /app\.js/);
  assert.match(page.headers.get('content-security-policy'), /frame-ancestors 'none'/);
  assert.equal(page.headers.get('cache-control'), 'no-store');
  assert.equal((await fetch(f.origin + '/api/catalog')).status, 401);
  assert.equal((await fetch(f.origin + '/api/catalog', { headers: { Authorization: 'Bearer wrong' } })).status, 401);
  assert.equal(f.calls.length, 0);
  assert.equal((await f.get('/api/catalog')).status, 200);
  assert.equal(f.calls[0].sessionID, 'session');
  assert.equal(f.calls[0].project, '/chosen/project');
});

test('cross-origin, rebinding, writes and arbitrary paths cannot access the backend', async t => {
  const f = await fixture(t);
  assert.equal((await f.get('/api/catalog', { headers: { ...f.headers, Origin: 'https://evil.example' } })).status, 403);
  const rebinding = await new Promise((resolve, reject) => {
    const req = request(f.origin + '/api/catalog', { headers: { ...f.headers, Host: 'evil.example' } }, response => { response.resume(); resolve(response.statusCode); });
    req.on('error', reject); req.end();
  });
  assert.equal(rebinding, 403);
  assert.equal((await f.get('/api/catalog', { method: 'POST' })).status, 405);
  assert.equal((await f.get('/api/approve')).status, 404);
  assert.equal((await f.get('/api/inspect?id=../../.env')).status, 404);
  assert.equal(f.calls.length, 0);
  await f.get('/api/catalog');
  await f.get('/api/inspect?id=asset-key&path=/etc/passwd&project=/other&sessionID=other');
  assert.deepEqual(f.calls.at(-1), { sessionID: 'session', project: '/chosen/project', action: 'inspect', path: 'art/dot', kind: 'sprite', revision_hash: 'a'.repeat(64) });
});

test('refresh replaces the catalog and stale asset keys are refused', async t => {
  let assets = [entry];
  const f = await fixture(t, async () => ({ ok: true, assets }));
  await f.get('/api/catalog');
  assets = [{ ...entry, id: 'new-key', path: 'art/new' }];
  await f.get('/api/catalog');
  assert.equal((await f.get('/api/inspect?id=asset-key')).status, 404);
  assert.equal((await f.get('/api/inspect?id=new-key')).status, 200);
  assert.equal(f.calls.at(-1).path, 'art/new');
});

test('project images are content-bound after their first successful inspection', async t => {
  const image = { id: 'image', path: 'assets/icon.png', kind: 'image' };
  const f = await fixture(t, async input => input.action === 'catalog' ? { ok: true, assets: [image] } : { ok: true, revision_hash: 'b'.repeat(64) });
  await f.get('/api/catalog');
  await f.get('/api/inspect?id=image');
  await f.get('/api/media?id=image');
  assert.equal(f.calls.at(-1).revision_hash, 'b'.repeat(64));
});

test('manager reuses a project endpoint, separates sessions, and closes its listeners', async () => {
  const opened = [];
  const manager = createDashboardManager(async () => ({ ok: true, assets: [] }), async url => opened.push(url));
  try {
    await manager.open('a', '/project'); await manager.open('a', '/project'); await manager.open('b', '/project');
    assert.equal(opened[0], opened[1]); assert.notEqual(opened[1], opened[2]);
  } finally { await manager.dispose(); }
  await assert.rejects(fetch(new URL(opened[0]).origin));
  await assert.rejects(manager.open('a', '/project'), /closed/);
});

test('closing a dashboard aborts its in-flight native read', async t => {
  let started, signal;
  const ready = new Promise(resolve => { started = resolve; });
  const f = await fixture(t, async (_input, options) => {
    signal = options.signal; started();
    return new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(new Error('cancelled')), { once: true }));
  });
  const reading = f.get('/api/catalog').catch(error => error);
  await ready;
  await f.bridge.dispose();
  assert.equal(signal.aborted, true);
  assert.ok(await reading instanceof Error);
});

test('real service resolves exact read grants and rejects a moved session', { skip: !pillow }, async t => {
  const root = await mkdtemp(path.join(os.tmpdir(), 'daydream-dashboard-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const created = spawnSync(python, [path.join(checkout, 'tests/review_fixture.py'), root], { encoding: 'utf8' });
  assert.equal(created.status, 0, created.stderr);
  let directory = root, deny = false;
  const permissions = [];
  const service = createDashboardService({ location: { directory: root }, session: { get: async () => ({ location: { directory } }) },
    permission: { assert: async request => { permissions.push(request); if (deny) throw new Error('denied'); } } }, createRunner(checkout, { python }));
  t.after(() => service.dispose());
  const catalog = await service.call({ sessionID: 'session', project: root, action: 'catalog' });
  assert.equal(catalog.assets.length, 3);
  const asset = catalog.assets.find(item => item.kind === 'animation');
  const detail = await service.call({ sessionID: 'session', project: root, action: 'inspect', path: asset.path, kind: asset.kind, revision_hash: asset.revision_hash });
  assert.equal(detail.animations[0].name, 'idle');
  assert.ok(permissions.every(request => request.action === 'read'));
  deny = true;
  await assert.rejects(service.call({ sessionID: 'session', project: root, action: 'catalog' }), /denied/);
  deny = false; directory = os.tmpdir();
  await assert.rejects(service.call({ sessionID: 'session', project: root, action: 'catalog' }), /moved projects/);
});
