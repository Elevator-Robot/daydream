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
import { assetsCommand } from '../plugins/daydream-tools/assets-command.js';
import { pickAsset } from '../plugins/daydream-tools/asset-picker.js';

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
  return { root, permissions, reviews, call, advance: () => { time += 21 * 60 * 1000; }, setDeniedAction: action => { deny = action; } };
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
  const followup = await f.call({ action: 'changes', ticket: second.ticket, reviewer: 'test', feedback: 'Also make the eyes brighter' });
  assert.deepEqual(followup.status.feedback.notes.map(note => note.feedback), ['Make the outline darker', 'Also make the eyes brighter']);
  const repeated = await f.call({ action: 'changes', ticket: second.ticket, reviewer: 'test', feedback: 'Also make the eyes brighter' });
  assert.equal(repeated.result.action, 'keep_feedback');
  assert.equal(repeated.status.feedback.notes.length, 2);
  await assert.rejects(f.call({ action: 'approve', ticket: second.ticket, reviewer: 'test' }), /Changes were requested/);
  await assert.rejects(f.call({ action: 'plan', ticket: second.ticket }), /Only this exact approved/);
  assert.equal(JSON.parse(await readFile(path.join(f.root, 'art/dot/changes-requested.json'))).feedback, 'Make the outline darker');
});

test('revision handoff uses the selected exact asset and all latest notes for every kind without writes', { skip: !pillow }, async t => {
  const f = await fixture(t);
  for (const [kind, bundle] of [['sprite', 'art/dot'], ['animation', 'art/walk'], ['tileset', 'art/floor']]) {
    const opened = await f.call({ action: 'open', bundle });
    await assert.rejects(f.call({ action: 'revise', ticket: opened.ticket }), /Save your requested changes/);
    await f.call({ action: 'changes', ticket: opened.ticket, reviewer: 'user', feedback: 'Darker please' });
    const original = await readFile(path.join(f.root, bundle, 'changes-requested.json'));
    // Another open review adds feedback after the first viewer was prepared.
    const second = await f.call({ action: 'open', bundle });
    await f.call({ action: 'changes', ticket: second.ticket, reviewer: 'user', feedback: 'Keep the eyes bright though' });
    f.permissions.length = 0;
    const request = await f.call({ action: 'revise', ticket: opened.ticket });
    const selected = JSON.parse(request.text.split('Selected asset and saved feedback (JSON):\n')[1]);
    assert.equal(selected.project, f.root);
    assert.equal(selected.bundle, path.join(f.root, bundle));
    assert.equal(selected.name, opened.name);
    assert.equal(selected.kind, kind);
    assert.equal(selected.revision_hash, opened.revision_hash);
    assert.deepEqual(selected.notes.map(note => note.feedback), ['Darker please', 'Keep the eyes bright though']);
    assert.match(request.text, /Do not approve or import/);
    assert.match(request.text, /review\.inspect/);
    assert.ok(f.permissions.length && f.permissions.every(item => item.action === 'read'));
    assert.deepEqual(await readFile(path.join(f.root, bundle, 'changes-requested.json')), original);
    await assert.rejects(readFile(path.join(f.root, bundle, 'approval.json')), { code: 'ENOENT' });
    await assert.rejects(f.reviews.call({ sessionID: 'different', action: 'revise', ticket: opened.ticket }), /does not belong/);
  }
  const opened = await f.call({ action: 'open', bundle: 'art/dot' });
  f.advance();
  await assert.rejects(f.call({ action: 'revise', ticket: opened.ticket }), /expired/);
});

test('revision handoff honors read denial and cancellation', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const opened = await f.call({ action: 'open', bundle: 'art/dot' });
  await f.call({ action: 'changes', ticket: opened.ticket, reviewer: 'user', feedback: 'Darker please' });
  f.setDeniedAction('read');
  await assert.rejects(f.call({ action: 'revise', ticket: opened.ticket }), /denied/);
  const controller = new AbortController(); controller.abort();
  await assert.rejects(f.reviews.call({ sessionID: 'test-session', action: 'revise', ticket: opened.ticket }, { signal: controller.signal }), /cancelled/);
});

test('comparison keeps approval bound to the selected candidate, never its earlier reference', { skip: !pillow }, async t => {
  const f = await fixture(t);
  const original = await f.call({ action: 'open', bundle: 'art/dot' });
  await f.call({ action: 'changes', ticket: original.ticket, reviewer: 'fixture', feedback: 'Darker please' });
  const edited = spawnSync(python, ['-c', `import sys,json;sys.path.insert(0,sys.argv[1]);from operations import execute
r=execute('sprite.edit',{'bundle':'art/dot','patch':{'schema_version':1,'operations':[{'op':'recolor','symbol':'a','color':'#123456'}]},'apply':True},sys.argv[2]);assert r['ok'],r
print(json.dumps(r['result']))`, path.join(checkout, 'scripts'), f.root], { encoding: 'utf8' });
  assert.equal(edited.status, 0, edited.stderr);
  const candidate = JSON.parse(edited.stdout);
  const opened = await f.call({ action: 'open', bundle: candidate.directory });
  assert.match(opened.html, /Compare with previous version/);
  assert.match(opened.html, /Darker please/);
  assert.equal(opened.revision_hash, candidate.revision_hash);
  await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'fixture' });
  assert.equal(JSON.parse(await readFile(path.join(candidate.directory, 'approval.json'))).revision_hash, candidate.revision_hash);
  await assert.rejects(readFile(path.join(f.root, 'art/dot/approval.json')), { code: 'ENOENT' });
  await assert.rejects(f.call({ action: 'approve', ticket: original.ticket, reviewer: 'fixture' }), /Changes were requested/);
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
  await assert.rejects(f.call({ action: 'revise', ticket: opened.ticket }), /Revision changed after preview/);
  await assert.rejects(f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'test' }), /Revision changed after preview/);
  await assert.rejects(readFile(path.join(f.root, 'art/dot/approval.json')), { code: 'ENOENT' });
});

function ui({ decisions = ['approve', 'cancel'], confirm = true, browserFails = false, kind } = {}) {
  const calls = [], toasts = [], prompts = ['test reviewer', '', ''];
  const status = { state: 'unreviewed' };
  const context = { ui: { router: { current: () => ({ type: 'session', sessionID: 'test' }) }, toast: { show: value => toasts.push(value) }, dialog: {
    confirm: async () => confirm, prompt: async () => prompts.shift(), alert: async () => {}, select: async () => decisions.shift(),
  } } };
  const call = async input => {
    calls.push(input);
    if (input.action === 'open') return { ok: true, ticket: 'ticket', name: 'dot', kind, html: '<h1>fixture</h1>', revision_hash: 'a'.repeat(64), status: { ...status } };
    if (input.action === 'approve') { status.state = 'approved'; return { ok: true, status: { ...status } }; }
    if (input.action === 'changes') { status.state = 'changes_requested'; return { ok: true, status: { ...status } }; }
    if (input.action === 'options') return { ok: true, initialized: true, targets: [] };
    if (input.action === 'plan') return { ok: true, plan: { create: ['assets/dot.png'], update: '.daydream/assets.json', plan_hash: 'b'.repeat(64) } };
    return { ok: true };
  };
  const command = assetsCommand(context, call, async () => ({ assets: [] }), { open: async () => { if (browserFails) throw new Error('browser failed'); } });
  return { command, calls, toasts, prompts };
}

test('user approval is explicit, retains exact hash, and does not auto-import', async () => {
  const f = ui();
  assert.equal(f.command.id, 'daydream.assets');
  assert.equal(f.command.title, 'Your assets');
  assert.deepEqual(f.command.slash, { name: 'assets', arguments: true });
  await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'approve', 'cancel']);
  assert.equal(f.calls[1].reviewer, 'test reviewer');
});

test('saved feedback is readable and follow-up prompts retain the earlier notes', async () => {
  const notes = [{ reviewer: 'user', feedback: 'Darker please', reviewed_at: '2026-11-08T00:00:00+00:00' }];
  const menus = [], alerts = [], calls = [], prompts = ['Also make the eyes brighter', 'user'];
  const choices = ['feedback', 'changes', 'cancel'];
  const context = { ui: {
    router: { current: () => ({ type: 'session', sessionID: 'test' }) }, toast: { show: () => {} },
    dialog: { confirm: async () => true, select: async input => { menus.push(input); return choices.shift(); },
      alert: async input => { alerts.push(input); }, prompt: async () => prompts.shift() },
  } };
  const status = () => ({ state: 'changes_requested', feedback: { ...notes[0], notes: [...notes] } });
  const command = assetsCommand(context, async input => {
    calls.push(input);
    if (input.action === 'open') return { ok: true, ticket: 'ticket', name: 'Slime', html: '<h1>fixture</h1>', revision_hash: 'a'.repeat(64), status: status() };
    if (input.action === 'changes') { notes.push({ reviewer: input.reviewer, feedback: input.feedback, reviewed_at: '2026-11-08T00:01:00+00:00' }); return { ok: true, result: { action: 'changes_requested' }, status: status() }; }
    return { ok: true };
  }, async () => ({ assets: [] }), { open: async () => {} });
  await command.run('art/slime');
  assert.match(menus[0].options.find(option => option.value === 'changes').title, /Add more feedback/);
  assert.equal(menus[0].options.find(option => option.value === 'approve').disabled, true);
  assert.equal(menus[0].options.find(option => option.value === 'plan').disabled, true);
  assert.match(alerts[0].message, /Darker please/);
  assert.equal(notes.length, 2);
  assert.deepEqual(calls.map(input => input.action), ['open', 'changes', 'cancel']);
});

function revisionUI({ choices = ['changes', 'revise'], prepare, send } = {}) {
  const calls = [], sent = [], menus = [], alerts = [], toasts = [], prompts = ['Darker please', 'user'];
  let sessionID = 'test', status = { state: 'unreviewed' };
  const context = { client: { session: { prompt: async input => { sent.push(input); await send?.(); } } }, ui: {
    router: { current: () => ({ type: 'session', sessionID }) }, toast: { show: input => toasts.push(input) },
    dialog: { confirm: async () => true, select: async input => { menus.push(input); return choices.shift(); },
      prompt: async () => prompts.shift(), alert: async input => alerts.push(input) },
  } };
  const command = assetsCommand(context, async input => {
    calls.push(input);
    if (input.action === 'open') return { ok: true, ticket: 'ticket', name: 'Selected floor', html: 'preview', status };
    if (input.action === 'changes') {
      status = { state: 'changes_requested', feedback: { notes: [{ reviewer: input.reviewer, feedback: input.feedback }] } };
      return { ok: true, result: { action: 'changes_requested' }, status };
    }
    if (input.action === 'revise') {
      await prepare?.(() => { sessionID = 'another-session'; });
      return { ok: true, text: 'Exact asset and complete feedback from server' };
    }
    return { ok: true };
  }, async () => ({ ok: true, assets: [{ name: 'Selected floor', bundle: 'art/floor', kind: 'tileset' }] }), { open: async () => {} });
  return { command, calls, sent, menus, alerts, toasts, prompts };
}

test('save feedback then make revised version returns to chat with one request and no name prompt', async () => {
  const f = revisionUI({ choices: ['art/floor', 'changes', 'revise'] });
  await f.command.run();
  assert.deepEqual(f.calls.map(input => input.action), ['open', 'changes', 'revise', 'cancel']);
  assert.deepEqual(f.sent, [{ sessionID: 'test', text: 'Exact asset and complete feedback from server' }]);
  assert.deepEqual(f.prompts, []); // Only the change text and reviewer were needed.
  assert.equal(f.menus.at(-1).current, 'revise');
  assert.equal(f.menus.at(-1).options.find(item => item.value === 'revise').disabled, false);
  assert.equal(f.toasts.at(-1).title, 'Revision request sent');
});

test('finishing review after saving feedback does not submit a model request', async () => {
  const f = revisionUI({ choices: ['changes', 'cancel'] });
  await f.command.run('art/floor');
  assert.equal(f.sent.length, 0);
  assert.deepEqual(f.calls.map(input => input.action), ['open', 'changes', 'cancel']);
});

test('failed validation and session changes during revision preparation never send', async () => {
  for (const prepare of [async () => { throw new Error('Review expired'); }, async move => move()]) {
    const f = revisionUI({ prepare });
    await f.command.run('art/floor');
    assert.equal(f.sent.length, 0);
    assert.equal(f.alerts.length, 1);
    assert.equal(f.toasts.at(-1).variant, 'error');
    assert.equal(f.calls.at(-1).action, 'cancel');
  }
});

test('failed prompt submission is reported without a retry or false success', async () => {
  const f = revisionUI({ send: async () => { throw new Error('Connection lost'); } });
  await f.command.run('art/floor');
  assert.equal(f.sent.length, 1);
  assert.match(f.alerts[0].message, /Check the chat before trying again/);
  assert.equal(f.toasts.some(item => item.title === 'Revision request sent'), false);
  assert.equal(f.calls.at(-1).action, 'cancel');
});

test('repeated command dispatch while submitting cannot duplicate the revision request', async () => {
  let finish;
  const f = revisionUI({ send: () => new Promise(resolve => { finish = resolve; }) });
  const running = f.command.run('art/floor');
  await new Promise(resolve => setImmediate(resolve));
  await f.command.run('art/floor');
  assert.equal(f.sent.length, 1);
  finish();
  await running;
});

test('browser failure, cancel and declined confirmation never decide', async () => {
  for (const options of [{ browserFails: true }, { decisions: ['cancel'] }, { confirm: false }]) {
    const f = ui(options); await f.command.run('art/dot');
    assert.equal(f.calls.some(call => ['approve', 'changes', 'import'].includes(call.action)), false);
  }
});

test('approved asset still requires separate plan and apply action', async () => {
  const f = ui({ decisions: ['approve', 'plan', 'copy', 'keep', 'apply', 'done'] }); await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'approve', 'options', 'plan', 'import']);
});

test('request changes records feedback without starting generation', async () => {
  const f = ui({ decisions: ['changes'] });
  f.prompts.splice(0, f.prompts.length, 'Shorten the nose', 'test reviewer');
  await f.command.run('art/dot');
  assert.deepEqual(f.calls.map(call => call.action), ['open', 'changes', 'cancel']);
  assert.equal(f.calls[1].feedback, 'Shorten the nose');
});

test('friendly import names are passed through, details are optional and applying is separate', async () => {
  const f = ui({ decisions: ['approve', 'plan', 'copy', 'rename', 'details', 'apply', 'done'] });
  f.prompts.splice(0, f.prompts.length, 'test reviewer', 'Potion Shop Floor!');
  await f.command.run('art/dot');
  const plan = f.calls.find(call => call.action === 'plan');
  assert.equal(plan.name, 'Potion Shop Floor!');
  assert.equal(plan.strategy, 'copy');
  assert.equal(f.calls.filter(call => call.action === 'import').length, 1);
});

test('asset picker exposes readable status and history without changing assets', async () => {
  const listed = [], dialogs = [], choices = ['\0history', 'art/old'];
  const context = { ui: { dialog: { select: async input => { dialogs.push(input); return choices.shift(); } } } };
  const selected = await pickAsset(context, async input => {
    listed.push(input);
    return { ok: true, assets: [{ name: 'Potion Shop Floor', bundle: input.history ? 'art/old' : 'art/current', kind: 'tileset', state: 'changes_requested', older_revisions: 3 }] };
  }, 'test-session');
  assert.equal(selected, 'art/old');
  assert.deepEqual(listed.map(input => input.history), [false, true]);
  assert.match(dialogs[0].options[0].description, /Needs changes/);
  assert.match(dialogs[0].options[0].description, /3 older/);
});

test('describing a new asset submits only the explicit user brief, never approval', async () => {
  const sent = [];
  const context = { client: { session: { prompt: async value => sent.push(value) } }, ui: {
    router: { current: () => ({ type: 'session', sessionID: 'test' }) }, toast: { show: () => {} },
    dialog: { select: async () => '\0create', prompt: async () => 'Mossy walls called Moonlight Floor' },
  } };
  await pickAsset(context, async () => ({ ok: true, assets: [] }), 'test');
  assert.equal(sent.length, 1);
  assert.equal(sent[0].sessionID, 'test');
  assert.match(sent[0].text, /Mossy walls called Moonlight Floor/);
  assert.match(sent[0].text, /Do not approve or import/);
});

test('read-only preview picker cannot start asset creation', async () => {
  const sent = [], menus = [];
  const context = { client: { session: { prompt: async value => sent.push(value) } }, ui: {
    dialog: { select: async input => { menus.push(input); return '\0create'; } },
  } };
  await pickAsset(context, async () => ({ ok: true, assets: [] }), 'test', undefined, { readOnly: true });
  assert.equal(sent.length, 0);
  assert.equal(menus[0].options.some(item => item.value === '\0create'), false);
});

test('real service discovers safe updates and preserves prior bytes at stable paths', { skip: !pillow }, async t => {
  const f = await fixture(t);
  let opened = await f.call({ action: 'open', bundle: 'art/dot' });
  await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'synthetic user' });
  await f.call({ action: 'plan', ticket: opened.ticket });
  await f.call({ action: 'import', ticket: opened.ticket });
  const edited = spawnSync(python, ['-c', `import sys;sys.path.insert(0,sys.argv[1]);from operations import execute
r=execute('sprite.edit',{'bundle':'art/dot','patch':{'schema_version':1,'operations':[{'op':'recolor','symbol':'a','color':'#123456'}]},'apply':True},sys.argv[2]);assert r['ok'],r
print(r['result']['directory'])`, path.join(checkout, 'scripts'), f.root], { encoding: 'utf8' });
  assert.equal(edited.status, 0, edited.stderr);
  opened = await f.call({ action: 'open', bundle: edited.stdout.trim() });
  await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'synthetic user' });
  const choices = await f.call({ action: 'options', ticket: opened.ticket });
  assert.equal(choices.targets[0].can_update, true);
  const original = await readFile(path.join(f.root, 'assets/sprites/dot.png'));
  const planned = await f.call({ action: 'plan', ticket: opened.ticket, strategy: 'update', target: 'dot' });
  assert.ok(planned.plan.replace.includes('assets/sprites/dot.png'));
  const result = await f.call({ action: 'import', ticket: opened.ticket });
  assert.equal(result.result.asset_name, 'dot');
  assert.ok(f.permissions.some(request => request.action === 'daydream.asset.update'));
  assert.deepEqual(await readFile(path.join(f.root, result.result.history, 'files/assets/sprites/dot.png')), original);
});

test('refusal details remain in a dialog until dismissed and never retry import', async () => {
  const calls = [], alerts = [], decisions = ['plan', 'copy', 'keep', 'cancel'];
  let dismiss;
  const context = { ui: { router: { current: () => ({ type: 'session', sessionID: 'test' }) },
    toast: { show: () => {} }, dialog: {
      confirm: async () => true,
      select: async () => decisions.shift(),
      alert: async value => { alerts.push(value); await new Promise(resolve => { dismiss = resolve; }); },
    } } };
  const command = assetsCommand(context, async input => {
    calls.push(input.action);
    if (input.action === 'open') return { ok: true, ticket: 'test-ticket', name: 'floor', revision_hash: 'a'.repeat(64), status: { state: 'approved' }, html: '<h1>fixture</h1>' };
    if (input.action === 'options') return { ok: true, targets: [] };
    if (input.action === 'plan') return { ok: false, error: { message: 'Refusing to replace existing asset: art/tilesets/floor.json; use a new --name' } };
    return { ok: true };
  }, async () => ({ assets: [] }), { open: async () => {} });
  const running = command.run('art/floor');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(alerts.length, 1);
  assert.match(alerts[0].message, /Refusing to replace existing asset/);
  assert.deepEqual(calls, ['open', 'options', 'plan']);
  dismiss();
  await running;
  assert.deepEqual(calls, ['open', 'options', 'plan', 'cancel']);
});

test('tileset editor mode auto-detects Godot without path or version questions', async () => {
  const f = ui({ decisions: ['approve', 'plan', 'copy', 'keep', 'editor', 'apply', 'done'], kind: 'tileset' });
  f.prompts.splice(0, f.prompts.length, 'test reviewer');
  await f.command.run('art/floor');
  const plan = f.calls.find(call => call.action === 'plan');
  assert.equal(plan.layout, 'editor');
  assert.equal(plan.godot, undefined);
  assert.equal(plan.godot_version, undefined);
  assert.deepEqual(f.prompts, []);
});

test('user review service plans and applies script-free editor mode with engine permission', { skip: !pillow || !process.env.GODOT_BIN }, async t => {
  const f = await fixture(t);
  const opened = await f.call({ action: 'open', bundle: 'art/floor' });
  await f.call({ action: 'approve', ticket: opened.ticket, reviewer: 'synthetic engine fixture' });
  const binary = process.env.GODOT_BIN;
  const version = spawnSync(binary, ['--version'], { encoding: 'utf8' }).stdout.trim().match(/^4\.\d+\.\d+/)[0];
  const plan = await f.call({ action: 'plan', ticket: opened.ticket, layout: 'editor', godot: binary, godot_version: version });
  assert.equal(plan.plan.serialization.script_attached, false);
  assert.ok(f.permissions.some(request => request.action === 'daydream.engine.serialize'));
  await f.call({ action: 'import', ticket: opened.ticket });
  const scene = await readFile(path.join(f.root, 'assets/tilesets/floor.tscn'), 'utf8');
  assert.match(scene, /tile_map_data/);
  assert.doesNotMatch(scene, /script =/);
});
