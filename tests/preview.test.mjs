import { test } from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { PassThrough } from 'node:stream';
import { mkdtemp, mkdir, writeFile, readFile, rm, symlink } from 'node:fs/promises';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { createPreviewService } from '../plugins/daydream-tools/preview.js';
import { previewCommand } from '../plugins/daydream-tools/preview-command.js';
import { createBrowser } from '../plugins/daydream-tools/browser.js';
import { createRunner } from '../plugins/daydream-tools/runner.js';

const checkout = fileURLToPath(new URL('../', import.meta.url));
const python = process.env.DAYDREAM_TEST_PYTHON ?? 'python3';

async function fixture(t, { deny, version = '4.7.2.stable.test', exitCode } = {}) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'daydream-preview-test-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  await writeFile(path.join(root, 'project.godot'), '[application]\nrun/main_scene="res://main.tscn"\n');
  const permissions = [], spawned = [];
  const ctx = { location: { directory: root }, session: { get: async () => ({ location: { directory: root } }) },
    permission: { assert: async input => { permissions.push(input); if (deny === input.action) throw new Error('denied'); } } };
  const fakeSpawn = (binary, args, options) => {
    const child = new EventEmitter(); child.stdout = new PassThrough(); child.stderr = new PassThrough(); child.pid = 123;
    child.kill = signal => { child.killedWith = signal; process.nextTick(() => child.emit('close', null, signal)); return true; };
    spawned.push({ binary, args, options, child });
    process.nextTick(() => {
      child.emit('spawn');
      if (args.includes('--version')) { child.stdout.write(version); child.emit('close', 0); }
      else if (exitCode !== undefined) { child.stderr.write('fixture startup failed'); child.emit('close', exitCode); }
    });
    return child;
  };
  const service = createPreviewService(ctx, createRunner(checkout, { python }), fakeSpawn);
  t.after(() => service.dispose());
  const call = (action, extra = {}) => service.call({ sessionID: 'fixture', action, ...extra });
  return { root, ctx, service, call, permissions, spawned, fakeSpawn };
}

test('game launches graphical main scene, duplicate is refused, stop only owns its child', async t => {
  const f = await fixture(t);
  assert.equal((await f.call('status')).state, 'not_running');
  assert.equal((await f.call('game')).state, 'running');
  assert.deepEqual(f.spawned[1].args, ['--path', f.root]);
  assert.equal(f.spawned[1].options.shell, false);
  assert.equal((await f.call('game')).already_running, true);
  assert.equal(f.spawned.length, 2);
  assert.deepEqual(f.permissions.slice(0, 3).map(item => item.action), ['read', 'daydream.preview.game', 'edit']);
  assert.equal((await f.call('stop')).state, 'stopped');
  assert.equal(f.spawned[1].child.killedWith, 'SIGTERM');
  assert.equal((await f.call('status')).state, 'exited');
});

test('permissions block even the version executable, with no fallback', async t => {
  for (const deny of ['read', 'daydream.preview.game', 'edit']) {
    const f = await fixture(t, { deny });
    await assert.rejects(f.call('game'), /denied/);
    assert.equal(f.spawned.length, 0);
  }
});

test('pin mismatch and missing main scene fail without a game process', async t => {
  const f = await fixture(t);
  await mkdir(path.join(f.root, '.daydream'));
  await writeFile(path.join(f.root, '.daydream/preview.json'), JSON.stringify({ godot: '/engine with spaces/godot', version: '4.6.3' }));
  await assert.rejects(f.call('game'), /version mismatch/);
  assert.equal(f.spawned.length, 1);
  assert.equal(f.spawned[0].binary, '/engine with spaces/godot');
  await writeFile(path.join(f.root, 'project.godot'), '[application]\n');
  await assert.rejects(f.call('game'), /main scene/);
  assert.equal(f.spawned.length, 1);
});

test('immediate launch failures retain diagnostics and nonzero exit status', async t => {
  const f = await fixture(t, { exitCode: 1 });
  const result = await f.call('game');
  assert.equal(result.ok, false);
  assert.equal(result.state, 'failed');
  assert.match((await f.call('status')).diagnostics, /fixture startup failed/);
});

test('unload stops owned game; cancellation and concurrent starts do not duplicate', async t => {
  const f = await fixture(t);
  // Filesystem resolution is asynchronous: either request may acquire the lock.
  const starts = await Promise.allSettled([f.call('game'), f.call('game')]);
  assert.equal(starts.filter(result => result.status === 'fulfilled').length, 1);
  assert.match(starts.find(result => result.status === 'rejected').reason.message, /in progress/);
  await f.service.dispose();
  assert.equal(f.spawned[1].child.killedWith, 'SIGTERM');
  const g = await fixture(t);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(g.service.call({ sessionID: 'fixture', action: 'game' }, { signal: controller.signal }), /cancelled/);
  assert.equal(g.spawned.length, 0);
});

test('source discovery uses configured source root and ignores symlink candidates', async t => {
  const f = await fixture(t);
  await mkdir(path.join(f.root, '.daydream'));
  await writeFile(path.join(f.root, '.daydream/config.json'), JSON.stringify({ paths: { sources: 'custom art' } }));
  await mkdir(path.join(f.root, 'custom art/slime'), { recursive: true });
  await writeFile(path.join(f.root, 'custom art/slime/manifest.json'), JSON.stringify({ kind: 'sprite' }));
  await symlink('/etc', path.join(f.root, 'custom art/escape'), 'dir');
  const result = await f.call('assets');
  assert.deepEqual(result.assets, [{ bundle: 'custom art/slime', kind: 'sprite' }]);
  await assert.rejects(f.call('asset', { bundle: '../escape' }), /Invalid project path/);
  await assert.rejects(f.call('asset', { bundle: 'custom art/escape' }), /Symlinks/);
});

const pillow = spawnSync(python, ['-c', 'import PIL']).status === 0;
test('real sprite animation and tileset viewers embed validated images and never approve', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const recipe = JSON.stringify({ schema_version: 1, name: 'dot', width: 2, height: 2, palette: { a: '#ffffff' }, pixels: ['a.', '.a'] });
  const generated = spawnSync(python, ['-c', `import sys,json;sys.path.insert(0,${JSON.stringify(path.join(checkout, 'scripts'))});from operations import execute
root=sys.argv[1]
r=execute('sprite.create',{'source':json.loads(sys.argv[2]),'output':'art/dot','apply':True},root)
assert r['ok'],r
r=execute('animation.assemble',{'name':'walk','pivot':[1,2],'frames':[{'id':'a','bundle':'art/dot'}],'animations':[{'name':'idle','fps':4,'loop':True,'frames':[{'frame':'a','duration':1}]}],'default_animation':'idle','output':'art/walk','apply':True},root)
assert r['ok'],r
import tileset_core
seed={'schema_version':1,'name':'floor','width':4,'height':4,'palette':{'a':'#ffffff','b':'#444444'},'pixels':['aaaa']*4}
other={**seed,'name':'wall','pixels':['bbbb']*4}
tiles=tileset_core.transitions(seed,other,'terrain',['floor','wall'])
r=execute('tileset.create',{'source':tiles,'output':'art/terrain','apply':True},root)
assert r['ok'],r
r=execute('tileset.edit',{'bundle':'art/terrain','tiles':[{'id':'tile-1-15','collision_preset':{'preset':'platform','one_way_margin':0.5}}],'output':'art/terrain-shapes','apply':True},root)
assert r['ok'],r`, f.root, recipe], { encoding: 'utf8' });
  assert.equal(generated.status, 0, generated.stderr);
  for (const bundle of ['art/dot', 'art/walk', 'art/terrain', 'art/terrain-shapes']) {
    const viewer = await f.call('asset', { bundle });
    assert.match(viewer.html, /data:image\/png;base64,/);
    assert.match(viewer.html, /does not approve or import/);
    assert.match(viewer.html, /Content-Security-Policy/);
    assert.equal(viewer.revision_hash.length, 64);
    if (bundle === 'art/terrain-shapes') {
      assert.match(viewer.html, /Collision coverage/);
      assert.match(viewer.html, /Exact collision geometry/);
      assert.match(viewer.html, /one_way_margin/);
    }
    await assert.rejects(readFile(path.join(f.root, bundle, 'approval.json')), { code: 'ENOENT' });
  }
  await writeFile(path.join(f.root, 'art/dot/preview.png'), 'tampered');
  await assert.rejects(f.call('asset', { bundle: 'art/dot' }));
});

test('browser opens local self-contained file with argv and cleans only its own directory', async t => {
  const f = await fixture(t);
  const opened = [];
  const browser = createBrowser((binary, args, options) => {
    opened.push({ binary, args, options });
    const child = new EventEmitter(); child.kill = () => {};
    process.nextTick(() => child.emit('close', 0)); return child;
  }, f.root);
  const file = await browser.open('<!doctype html><h1>fixture</h1>');
  assert.match(await readFile(file, 'utf8'), /fixture/);
  assert.match(opened[0].args[0], /^file:/);
  assert.equal(opened[0].options.shell, false);
  await browser.dispose();
  await assert.rejects(readFile(file), { code: 'ENOENT' });
  assert.match(await readFile(path.join(f.root, 'project.godot'), 'utf8'), /main_scene/);
});

test('long-lived desktop opener is accepted without killing the viewer', async t => {
  const f = await fixture(t);
  let detached = false;
  const browser = createBrowser(() => {
    const child = new EventEmitter();
    child.unref = () => { detached = true; };
    child.kill = () => { throw new Error('Must not kill the user browser'); };
    return child;
  }, f.root);
  await browser.open('<!doctype html><h1>fixture</h1>');
  assert.equal(detached, true);
  await browser.dispose();
});

function commandFixture({ confirm = true, selection = 'game' } = {}) {
  const calls = [], toasts = [], opened = [];
  const context = { ui: { router: { current: () => ({ type: 'session', sessionID: 'selected' }) },
    toast: { show: value => toasts.push(value) }, dialog: {
      confirm: async () => confirm, select: async () => selection, alert: async () => {},
    } } };
  const command = previewCommand(context, async input => { calls.push(input); return { ok: true, state: 'running', html: '<h1>viewer</h1>' }; }, { open: async html => opened.push(html) });
  return { command, calls, toasts, opened };
}

test('slash picker launches without prompting the model; cancel does nothing', async () => {
  const accepted = commandFixture(); await accepted.command.run();
  assert.deepEqual(accepted.calls, [{ sessionID: 'selected', action: 'game' }]);
  const cancelled = commandFixture({ confirm: false }); await cancelled.command.run('game');
  assert.equal(cancelled.calls.length, 0);
});

test('slash arguments preserve path spaces and open assets only after confirmation', async () => {
  const f = commandFixture(); await f.command.run('asset art/my  sprites/slime');
  assert.equal(f.calls[0].bundle, 'art/my  sprites/slime');
  assert.equal(f.opened.length, 1);
  await f.command.run('stop');
  assert.equal(f.calls[1].action, 'stop');
  await f.command.run('unknown');
  assert.equal(f.calls.length, 2);
  assert.equal(f.toasts.at(-1).variant, 'error');
});

test('real graphical Godot starts and stops an isolated synthetic scene', { skip: process.env.DAYDREAM_GRAPHICAL_TEST !== '1' }, async t => {
  const f = await fixture(t);
  await mkdir(path.join(f.root, '.daydream'));
  await writeFile(path.join(f.root, '.daydream/preview.json'), JSON.stringify({ godot: process.env.GODOT_BIN ?? 'godot' }));
  await writeFile(path.join(f.root, 'project.godot'), 'config_version=5\n[application]\nconfig/name="Daydream preview fixture"\nrun/main_scene="res://main.tscn"\n[display]\nwindow/size/viewport_width=320\nwindow/size/viewport_height=240\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n');
  await writeFile(path.join(f.root, 'main.tscn'), '[gd_scene format=3]\n[node name="PreviewFixture" type="Node2D"]\n');
  const service = createPreviewService(f.ctx, createRunner(checkout, { python }), spawn);
  t.after(() => service.dispose());
  const started = await service.call({ sessionID: 'fixture', action: 'game' });
  assert.equal(started.state, 'running', JSON.stringify(started));
  const stopped = await service.call({ sessionID: 'fixture', action: 'stop' });
  assert.equal(stopped.state, 'stopped');
  assert.equal((await service.call({ sessionID: 'fixture', action: 'status' })).state, 'exited');
});
