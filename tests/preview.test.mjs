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
import { assetViewer, olderVersions, viewerScript, HISTORY_LIMIT } from '../plugins/daydream-tools/asset-viewer.js';
import { createHash } from 'node:crypto';
import { runInNewContext } from 'node:vm';

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
  const launched = await f.call('game');
  assert.equal(launched.state, 'running');
  // RPC validates JSON values before serializing: present-but-undefined fields
  // fail there even though the native tool's JSON.stringify silently drops them.
  assert.deepEqual(launched, JSON.parse(JSON.stringify(launched)));
  assert.equal(Object.hasOwn(launched, 'code'), false);
  assert.equal(Object.hasOwn(launched, 'signal'), false);
  const running = await f.call('status');
  assert.deepEqual(running, JSON.parse(JSON.stringify(running)));
  assert.deepEqual(f.spawned[1].args, ['--path', f.root]);
  assert.equal(f.spawned[1].options.shell, false);
  const repeated = await f.call('game');
  assert.equal(repeated.already_running, true);
  assert.deepEqual(repeated, JSON.parse(JSON.stringify(repeated)));
  assert.equal(f.spawned.length, 2);
  assert.deepEqual(f.permissions.slice(0, 3).map(item => item.action), ['read', 'daydream.preview.game', 'edit']);
  assert.equal((await f.call('stop')).state, 'stopped');
  assert.equal(f.spawned[1].child.killedWith, 'SIGTERM');
  const exited = await f.call('status');
  assert.equal(exited.state, 'exited');
  assert.equal(exited.code, null);
  assert.equal(exited.signal, 'SIGTERM');
  assert.deepEqual(exited, JSON.parse(JSON.stringify(exited)));
});

test('post-import scene preview uses explicit argv without changing the main scene', async t => {
  const f = await fixture(t);
  const before = await readFile(path.join(f.root, 'project.godot'));
  await mkdir(path.join(f.root, 'assets'));
  await writeFile(path.join(f.root, 'assets/test.tscn'), '[gd_scene format=3]\n[node name="Fixture" type="Node2D"]\n');
  const result = await f.call('game', { scene: 'assets/test.tscn' });
  assert.equal(result.state, 'running');
  assert.deepEqual(f.spawned[1].args, ['--path', f.root, 'res://assets/test.tscn']);
  assert.deepEqual(await readFile(path.join(f.root, 'project.godot')), before);
  await assert.rejects(f.call('game'), /Another preview/);
  await f.call('stop');
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

test('immediate exits retain zero/nonzero codes and JSON-safe status diagnostics', async t => {
  for (const exitCode of [0, 1]) {
    const f = await fixture(t, { exitCode });
    const result = await f.call('game');
    assert.equal(result.ok, exitCode === 0);
    assert.equal(result.state, exitCode === 0 ? 'exited' : 'failed');
    assert.equal(result.code, exitCode);
    assert.deepEqual(result, JSON.parse(JSON.stringify(result)));
    const status = await f.call('status');
    assert.equal(status.code, exitCode);
    assert.deepEqual(status, JSON.parse(JSON.stringify(status)));
    if (exitCode !== 0) assert.match(status.diagnostics, /fixture startup failed/);
  }
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
  await writeFile(path.join(f.root, '.daydream/config.json'), JSON.stringify({ schema_version: 1, paths: { sources: 'custom art', assets: 'assets' } }));
  await mkdir(path.join(f.root, 'custom art/slime'), { recursive: true });
  await writeFile(path.join(f.root, 'custom art/slime/manifest.json'), JSON.stringify({ kind: 'sprite', name: 'slime' }));
  await symlink('/etc', path.join(f.root, 'custom art/escape'), 'dir');
  const result = await f.call('assets');
  assert.equal(result.assets.length, 1);
  assert.equal(result.assets[0].bundle, 'custom art/slime');
  assert.equal(result.assets[0].kind, 'sprite');
  await assert.rejects(f.call('asset', { bundle: '../escape' }), /Invalid project path/);
  await assert.rejects(f.call('asset', { bundle: 'custom art/escape' }), /Symlinks/);
});

const pillow = spawnSync(python, ['-c', 'import PIL']).status === 0;

test('comparison prefers ancestry, excludes other assets/newer versions and deduplicates hashes', () => {
  const current = { id: 'floor', manifest_kind: 'tileset', revision_hash: 'current', parent_revision_hash: 'parent' };
  const row = (revision_hash, modified_at, extra = {}) => ({ id: 'floor', kind: 'tileset', revision_hash, modified_at, bundle: revision_hash, ...extra });
  const catalog = { assets: [row('newer', 100), row('parent', 90, { parent_revision_hash: 'first' }), row('current', 50),
    row('older-branch', 40), row('first', 30), row('first', 20), row('other-type', 10, { kind: 'sprite' }), row('other-name', 10, { id: 'wall' })] };
  const result = olderVersions(current, catalog);
  assert.deepEqual(result.previous.map(item => item.revision_hash), ['parent', 'first', 'older-branch']);
  assert.equal(result.isLatest, false);
  const missing = olderVersions({ ...current, parent_revision_hash: 'missing' }, catalog);
  assert.match(missing.previous[0].error, /could not be found/);
  assert.equal(missing.previous[0].revision_hash, 'missing');
  const bounded = olderVersions({ ...current, parent_revision_hash: undefined }, { assets: [row('current', 100), ...Array.from({ length: 20 }, (_, i) => row('old-' + i, 99 - i))] });
  assert.equal(bounded.previous.length, HISTORY_LIMIT);
  assert.equal(bounded.limited, true);
});

test('viewer escapes feedback/names, pins the selected revision and permits only its fixed script', () => {
  const hostile = '</script><script>alert(1)</script><img src=x onerror=alert(2)>';
  const current = { name: hostile, revision_hash: 'selected-hash', state: 'unreviewed', body: '<p>validated artwork</p>',
    notes: [{ reviewer: hostile, reviewed_at: hostile, feedback: hostile }], bundle: hostile };
  const html = assetViewer(current, [{ ...current, revision_hash: 'old-hash', modified_at: 1000000 }]);
  assert.equal((html.match(/<script>/g) ?? []).length, 1);
  assert.ok(html.includes("script-src 'sha256-" + createHash('sha256').update(viewerScript).digest('base64') + "'"));
  assert.equal(html.includes(hostile), false);
  assert.match(html, /data-reviewed-revision="selected-hash"/);
  assert.match(html, /Comparing older versions never changes the candidate under review/);
  assert.match(html, /id="older-version"/);
  assert.match(html, /width:calc\(var\(--pixel-width\)\*var\(--zoom\)\)/);
});

test('preview looping repeats visible one-shots, follows the toggle, and cleans up hidden/history timers', () => {
  const element = (values = {}) => ({ listeners: {}, addEventListener(type, handler) { this.listeners[type] = handler; },
    emit(type, event = {}) { this.listeners[type]?.({ target: this, ...event }); }, ...values });
  const elements = { compare: element({ open: false }), 'older-version': element({ value: '0' }), 'history-panel': element({ hidden: true }),
    panels: element({ classList: { toggle() {} } }), 'loop-preview': element({ checked: true }), 'replay-motion': element(), zoom: element() };
  const panes = [element({ dataset: { historyIndex: '0' }, hidden: false }), element({ dataset: { historyIndex: '1' }, hidden: true })];
  function image(loop, duration, frames = 2, pane) {
    let source = 'data:image/png;base64,YQ==';
    return { dataset: { loop: String(loop), durationMs: String(duration), visualFrames: String(frames) }, plays: 0,
      getClientRects: () => pane && (pane.hidden || elements['history-panel'].hidden) ? [] : [{}],
      get src() { return source; }, set src(value) { source = value; this.plays++; this.onload?.(); } };
  }
  const shot = image(false, 666), looping = image(true, 200), still = image(false, 300, 1);
  const reference = image(false, 900, 2, panes[0]), olderReference = image(false, 1200, 2, panes[1]);
  const images = [shot, looping, still, reference, olderReference];
  const timers = new Map(), revoked = [];
  let nextTimer = 0, nextURL = 0;
  const document = element({ hidden: false, getElementById: id => elements[id],
    querySelectorAll: selector => selector === 'img[data-motion]' ? images : panes,
    documentElement: { style: { setProperty() {} } } });
  const window = element();
  runInNewContext(viewerScript, { document, window, Blob, Uint8Array, atob,
    URL: { createObjectURL: () => 'blob:test-' + ++nextURL, revokeObjectURL: url => revoked.push(url) },
    setTimeout: (callback, duration) => { const id = ++nextTimer; timers.set(id, { callback, duration }); return id; },
    clearTimeout: id => timers.delete(id) });
  assert.deepEqual([...timers.values()].map(timer => timer.duration), [666]);
  const initialURL = shot.src, idlePlays = looping.plays;
  const [id, timer] = timers.entries().next().value;
  timers.delete(id); timer.callback();
  assert.notEqual(shot.src, initialURL);
  assert.ok(revoked.includes(initialURL));
  assert.equal(looping.plays, idlePlays); // The attack's replay never restarts native idle loops.
  assert.equal(reference.plays, 0);
  assert.equal(timers.size, 1);
  elements['loop-preview'].checked = false;
  elements['loop-preview'].emit('change');
  assert.equal(timers.size, 0);
  const beforeReplay = shot.plays;
  elements['replay-motion'].emit('click');
  assert.equal(shot.plays, beforeReplay + 1);
  assert.equal(timers.size, 0);
  elements['loop-preview'].checked = true;
  elements['loop-preview'].emit('change');
  elements.compare.open = true; elements.compare.emit('toggle');
  assert.deepEqual([...timers.values()].map(timer => timer.duration), [666, 900]);
  elements['older-version'].value = '1'; elements['older-version'].emit('change');
  assert.deepEqual([...timers.values()].map(timer => timer.duration), [666, 1200]);
  document.hidden = true; document.emit('visibilitychange');
  assert.equal(timers.size, 0);
  document.hidden = false; document.emit('visibilitychange');
  assert.equal(timers.size, 2);
  const lateLoad = shot.onload;
  window.emit('pagehide'); lateLoad();
  assert.equal(timers.size, 0);
  window.emit('pageshow', { persisted: true });
  assert.equal(timers.size, 2);
});

test('preview-only looping retains source bytes and uses the actual rounded clip duration', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const generated = spawnSync(python, ['-c', `import sys,json
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2]);from review_fixture import create;from operations import execute
root=sys.argv[3];create(root)
recipe={'schema_version':1,'name':'One Shot','pivot':[2,4],'frames':[{'id':'rest'},{'id':'flash','pixels':['bbbb']*4}],'animations':[{'name':'attack','fps':3,'loop':False,'frames':[{'frame':'rest','duration':1},{'frame':'flash','duration':1}]}],'default_animation':'attack'}
r=execute('animation.create',{'base':'art/dot','recipe':recipe,'apply':True},root);assert r['ok'],r
bundle=r['result']['directory'];r=execute('animation.inspect',{'bundle':bundle},root);assert r['ok'],r
print(json.dumps({'bundle':bundle,'inspected':r['result']}))`, path.join(checkout, 'scripts'), path.join(checkout, 'tests'), f.root], { encoding: 'utf8' });
  assert.equal(generated.status, 0, generated.stderr);
  const { bundle, inspected } = JSON.parse(generated.stdout);
  assert.equal(inspected.previews[0].duration_ms, 666);
  assert.equal(inspected.previews[0].loop, false);
  const files = ['source.json', 'manifest.json', 'attack.motion.png'];
  const before = await Promise.all(files.map(file => readFile(path.join(bundle, file))));
  const viewer = await f.call('asset', { bundle });
  assert.match(viewer.html, /id="loop-preview" type="checkbox" checked/);
  assert.match(viewer.html, /data-loop="false" data-duration-ms="666" data-visual-frames="2"/);
  assert.match(viewer.html, /Saved playback: plays once/);
  assert.match(viewer.html, /review only/);
  assert.deepEqual(await Promise.all(files.map(file => readFile(path.join(bundle, file)))), before);
  await assert.rejects(readFile(path.join(bundle, 'approval.json')), { code: 'ENOENT' });
});

test('all asset kinds compare validated prior revisions and saved notes without changing review target', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const generated = spawnSync(python, ['-c', `import sys,json
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
from review_fixture import create
from operations import execute
root=sys.argv[3];bundles=create(root);result={}
def call(op,data):
 r=execute(op,data,root);assert r['ok'],r;return r['result']
for kind,bundle in bundles.items():
 revision=call('review.inspect',{'kind':kind,'bundle':bundle})['revision_hash']
 call('review.feedback',{'kind':kind,'bundle':bundle,'revision_hash':revision,'reviewer':'fixture','feedback':'Darken the edges <not a tag>','apply':True})
 change={'recolor':{'symbol':'a','color':'#556677'}} if kind=='tileset' else {'patch':{'schema_version':1,'operations':[{'op':'recolor','symbol':'a','color':'#556677'}]}}
 if kind=='tileset':change['tiles']=[]
 second=call(kind+'.edit',{'bundle':bundle,**change,'apply':True})
 call('review.feedback',{'kind':kind,'bundle':second['directory'],'revision_hash':second['revision_hash'],'reviewer':'fixture','feedback':'Keep the middle bright','apply':True})
 change={'recolor':{'symbol':'a','color':'#112233'},'tiles':[]} if kind=='tileset' else {'patch':{'schema_version':1,'operations':[{'op':'recolor','symbol':'a','color':'#112233'}]}}
 third=call(kind+'.edit',{'bundle':second['directory'],**change,'apply':True})
 result[kind]={'original':bundle,'original_hash':revision,'second':second,'third':third}
print(json.dumps(result))`, path.join(checkout, 'scripts'), path.join(checkout, 'tests'), f.root], { encoding: 'utf8' });
  assert.equal(generated.status, 0, generated.stderr);
  const bundles = JSON.parse(generated.stdout);
  for (const [kind, versions] of Object.entries(bundles)) {
    const original = path.join(f.root, versions.original, 'changes-requested.json');
    const before = await readFile(original);
    const viewer = await f.call('asset', { bundle: versions.third.directory });
    assert.equal(viewer.kind, kind);
    assert.equal(viewer.revision_hash, versions.third.revision_hash);
    assert.match(viewer.html, /Compare with previous version/);
    assert.match(viewer.html, /Darken the edges &lt;not a tag&gt;/);
    assert.match(viewer.html, /Keep the middle bright/);
    assert.match(viewer.html, /data-history-index="1"/);
    assert.ok(viewer.html.indexOf(versions.second.revision_hash) < viewer.html.indexOf(versions.original_hash));
    assert.ok(viewer.html.includes(`data-reviewed-revision="${versions.third.revision_hash}"`));
    assert.match(viewer.html, /--pixel-width:4px/); // APNG's embedded 4x pixels are normalized too.
    assert.deepEqual(await readFile(original), before);
    await assert.rejects(readFile(path.join(versions.third.directory, 'approval.json')), { code: 'ENOENT' });
    const oldest = await f.call('asset', { bundle: versions.original });
    assert.doesNotMatch(oldest.html, /id="older-version"/);
    assert.match(oldest.html, /Selected version/);
  }
  const versions = bundles.sprite;
  await writeFile(path.join(versions.second.directory, 'sprite.png'), 'tampered');
  const partial = await f.call('asset', { bundle: versions.third.directory });
  assert.equal(partial.revision_hash, versions.third.revision_hash);
  assert.match(partial.html, /Cannot preview this earlier version/);
  assert.match(partial.html, /Darken the edges &lt;not a tag&gt;/); // Other history remains usable.
  await writeFile(path.join(versions.third.directory, 'sprite.png'), 'tampered');
  await assert.rejects(f.call('asset', { bundle: versions.third.directory }));
  assert.ok(f.permissions.every(item => item.action === 'read'));
  assert.equal(f.spawned.length, 0);
});

test('comparison metadata denial is explicit and does not retry or hide the selected asset', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const generated = spawnSync(python, [path.join(checkout, 'tests/review_fixture.py'), f.root], { encoding: 'utf8' });
  assert.equal(generated.status, 0, generated.stderr);
  let denied = 0;
  f.ctx.permission.assert = async input => {
    if (input.resources.some(file => file.endsWith('/.daydream/assets.json'))) { denied++; throw new Error('history read denied'); }
  };
  const viewer = await f.call('asset', { bundle: 'art/dot' });
  assert.match(viewer.html, /Version comparison unavailable: history read denied/);
  assert.match(viewer.html, /Candidate under review/);
  assert.equal(denied, 1);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(f.service.call({ sessionID: 'fixture', action: 'asset', bundle: 'art/dot' }, { signal: controller.signal }));
});
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
  const gallery = await f.call('gallery');
  assert.match(gallery.html, /Your assets/);
  assert.match(gallery.html, /data:image\/png;base64,/);
  assert.match(gallery.html, /Content-Security-Policy/);
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

test('preview no longer accepts the removed review route', async () => {
  const f = commandFixture();
  await f.command.run('review art/tiles/floor');
  assert.equal(f.calls.length, 0);
  assert.equal(f.opened.length, 0);
  assert.equal(f.toasts.at(-1).variant, 'error');
  assert.match(f.toasts.at(-1).message, /Manage artwork with \/assets/);
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
