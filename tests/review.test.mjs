import { test } from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtemp, readFile, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRunner } from '../plugins/daydream-tools/runner.js';
import { createReviewService } from '../plugins/daydream-tools/review.js';
import { createPreviewService } from '../plugins/daydream-tools/preview.js';
import { reviewCommand } from '../plugins/daydream-tools/review-command.js';

const checkout = fileURLToPath(new URL('../', import.meta.url));
const python = process.env.DAYDREAM_TEST_PYTHON ?? 'python3';
const pillow = spawnSync(python, ['-c', 'import PIL']).status === 0;

async function fixture(t, deny) {
  const root = await mkdtemp(path.join(os.tmpdir(), 'daydream-review-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const generated = spawnSync(python, [path.join(checkout, 'tests/review_fixture.py'), root], { encoding: 'utf8' });
  assert.equal(generated.status, 0, generated.stderr);
  const permissions = [];
  const ctx = { location: { directory: root }, session: { get: async () => ({ location: { directory: root } }) },
    permission: { assert: async request => { permissions.push(request); if (request.action === deny) throw new Error('denied'); } } };
  const native = createRunner(checkout, { python });
  const run = createRunner(checkout, { python }, undefined, 'review_ui');
  const previews = createPreviewService(ctx, native);
  let time = 1000;
  const reviews = createReviewService(ctx, run, previews, () => time);
  t.after(() => reviews.dispose());
  const call = input => reviews.call({ sessionID: 'test-session', ...input });
  return { root, permissions, reviews, call, advance: () => { time += 21 * 60 * 1000; } };
}

test('all three asset kinds review approve plan and import through one service', { skip: !pillow }, async t => {
  const f = await fixture(t);
  for (const [kind, bundle] of [['sprite', 'art/dot'], ['animation', 'art/walk'], ['tileset', 'art/floor']]) {
    const opened = await f.call({ action: 'open', bundle });
    assert.equal(opened.kind, kind);
    assert.equal(opened.status.state, 'unreviewed');
    assert.match(opened.html, /data:image\/png;base64/);
    const approved = await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'synthetic fixture user' });
    assert.equal(approved.status.state, 'approved');
    await assert.rejects(readFile(path.join(f.root, bundle, 'changes-requested.json')), { code: 'ENOENT' });
    await assert.rejects(f.call({ action: 'import', ticket: opened.ticket }), /plan first/);
    const plan = await f.call({ action: 'plan', ticket: opened.ticket });
    assert.equal(plan.plan.plan_hash.length, 64);
    await assert.rejects(readFile(path.join(f.root, plan.plan.create[0])), { code: 'ENOENT' });
    const imported = await f.call({ action: 'import', ticket: opened.ticket });
    assert.equal(imported.state, 'imported');
    await assert.rejects(f.call({ action: 'import', ticket: opened.ticket }), /expired/);
  }
  const consent = f.permissions.find(request => request.action === 'daydream.review.approve');
  assert.deepEqual(consent.save, []);
  assert.match(consent.resources[0], /#[0-9a-f]{64}$/);
});

test('changes are retained and block further approval/import, cancel writes nothing', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const opened = await f.call({ action: 'open', bundle: 'art/dot' });
  await f.call({ action: 'cancel', ticket: opened.ticket });
  await assert.rejects(readFile(path.join(f.root, 'art/dot/approval.json')), { code: 'ENOENT' });
  const second = await f.call({ action: 'open', bundle: 'art/dot' });
  const changed = await f.call({ action: 'changes', ticket: second.ticket, reviewer: 'test', feedback: 'Make the outline darker' });
  assert.equal(changed.status.state, 'changes_requested');
  await assert.rejects(f.call({ action: 'approve', ticket: second.ticket, reviewer: 'test' }), /Changes were requested/);
  await assert.rejects(f.call({ action: 'plan', ticket: second.ticket }), /Only this exact approved/);
  assert.equal(JSON.parse(await readFile(path.join(f.root, 'art/dot/changes-requested.json'))).feedback, 'Make the outline darker');
});

test('permission denial does not write approval and tickets expire', { skip: !pillow }, async t => {
  for (const deny of ['daydream.review.approve', 'edit']) {
    const f = await fixture(t, deny);
    const opened = await f.call({ action: 'open', bundle: 'art/dot' });
    await assert.rejects(f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'test' }), /denied/);
    await assert.rejects(readFile(path.join(f.root, 'art/dot/approval.json')), { code: 'ENOENT' });
    f.advance();
    await assert.rejects(f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'test' }), /expired/);
  }
});

test('plan changes, cross-session tickets and interruption cannot apply', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const opened = await f.call({ action: 'open', bundle: 'art/dot' });
  await assert.rejects(f.reviews.call({ sessionID: 'another-session', action: 'approve', ticket: opened.ticket, reviewer: 'test' }), /does not belong/);
  await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'test' });
  const planned = await f.call({ action: 'plan', ticket: opened.ticket });
  const config = path.join(f.root, '.daydream/config.json');
  const data = JSON.parse(await readFile(config)); data.paths.assets = 'different-assets';
  await writeFile(config, JSON.stringify(data));
  await assert.rejects(f.call({ action: 'import', ticket: opened.ticket }), /plan changed/);
  await assert.rejects(readFile(path.join(f.root, planned.plan.create[0])), { code: 'ENOENT' });
  const controller = new AbortController(); controller.abort();
  await assert.rejects(f.reviews.call({ sessionID: 'test-session', action: 'plan', ticket: opened.ticket }, { signal: controller.signal }), /cancelled/);
});

test('revision mutation after viewer creation invalidates the decision ticket', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const opened = await f.call({ action: 'open', bundle: 'art/dot' });
  // Simulate another local writer replacing the whole candidate with a valid
  // new revision, not only corrupting a file that the normal inspector rejects.
  const changed = spawnSync(python, ['-c', `import sys,json;from pathlib import Path
sys.path.insert(0,sys.argv[1]);import sprite_core as core
bundle=Path(sys.argv[2]);source=json.loads((bundle/'source.json').read_text());source['pixels'][0]='bbbb'
files=core.make_revision(source,{'method':'pixel-spec','input_sha256':core.digest(core.encoded(source)),'license':None})
for name,data in files.items():(bundle/name).write_bytes(data)
`, path.join(checkout, 'scripts'), path.join(f.root, 'art/dot')], { encoding: 'utf8' });
  assert.equal(changed.status, 0, changed.stderr);
  await assert.rejects(f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'test' }), /Revision changed after preview/);
  await assert.rejects(readFile(path.join(f.root, 'art/dot/approval.json')), { code: 'ENOENT' });
});

function ui({ decisions = ['approve', 'cancel'], confirm = true, browserFails = false } = {}) {
  const calls = [], toasts = [], prompts = ['test reviewer', '', ''];
  const status = { state: 'unreviewed' };
  const context = { ui: { router: { current: () => ({ type: 'session', sessionID: 'test' }) }, toast: { show: value => toasts.push(value) }, dialog: {
    confirm: async () => confirm, prompt: async () => prompts.shift(), alert: async () => {}, select: async () => decisions.shift(),
  } } };
  const call = async input => {
    calls.push(input);
    if (input.action === 'open') return { ok: true, ticket: 'ticket', name: 'dot', html: '<h1>fixture</h1>', revision_hash: 'a'.repeat(64), status: { ...status } };
    if (input.action === 'approve') { status.state = 'approved'; return { ok: true, status: { ...status } }; }
    if (input.action === 'changes') { status.state = 'changes_requested'; return { ok: true, status: { ...status } }; }
    if (input.action === 'plan') return { ok: true, plan: { create: ['assets/dot.png'], update: '.daydream/assets.json', plan_hash: 'b'.repeat(64) } };
    return { ok: true };
  };
  const command = reviewCommand(context, call, async () => ({ assets: [] }), { open: async () => { if (browserFails) throw new Error('browser failed'); } });
  return { command, calls, toasts, prompts };
}

test('user approval is explicit, retains exact hash, and does not auto-import', async () => {
  const f = ui();
  assert.equal(f.command.slash.name, 'asset-review');
  assert.equal(f.command.slash.aliases.includes('review'), false);
  await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'approve', 'cancel']);
  assert.equal(f.calls[1].reviewer, 'test reviewer');
});

test('browser failure, cancel and declined confirmation never decide', async () => {
  for (const options of [{ browserFails: true }, { decisions: ['cancel'] }, { confirm: false }]) {
    const f = ui(options); await f.command.run('art/dot');
    assert.equal(f.calls.some(call => ['approve', 'changes', 'import'].includes(call.action)), false);
  }
});

test('approved asset still requires separate plan and apply action', async () => {
  const f = ui({ decisions: ['approve', 'plan', 'defaults'] }); await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'approve', 'plan', 'import']);
});

test('request changes records feedback without starting generation', async () => {
  const f = ui({ decisions: ['changes'] });
  f.prompts.splice(0, f.prompts.length, 'Shorten the nose', 'test reviewer');
  await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'changes', 'cancel']);
  assert.equal(f.calls[1].feedback, 'Shorten the nose');
});
