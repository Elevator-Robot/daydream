import { spawn } from "node:child_process";
import { lstat, open, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";
import { assetViewer, feedbackHTML, olderVersions, VIEWER_BODY_LIMIT } from './asset-viewer.js';

const escape = (value) => String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
export class PreviewFailure extends Error {}
const fail = (message) => { throw new PreviewFailure(message); };

export async function projectPath(root, value) {
  if (typeof value !== 'string' || !value || /[\x00-\x1f\\]/.test(value) || value.split('/').includes('..')) fail('Invalid project path');
  const target = path.resolve(root, value);
  const relative = path.relative(root, target);
  if (relative === '..' || relative.startsWith('../') || path.isAbsolute(relative)) fail('Preview paths must stay inside the active project');
  let current = root;
  for (const part of relative.split('/').filter(Boolean)) {
    if (['.git', '.aws', '.ssh', '.config'].includes(part) || part === '.env' || part.startsWith('.env.')) fail('Sensitive configuration is not a preview asset');
    current = path.join(current, part);
    try { if ((await lstat(current)).isSymbolicLink()) fail('Symlinks are not allowed in preview paths'); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
  }
  return target;
}

async function read(file, limit = 1024 * 1024) {
  const handle = await open(file, constants.O_RDONLY | constants.O_NOFOLLOW | constants.O_NONBLOCK);
  try {
    const stat = await handle.stat();
    if (!stat.isFile() || stat.size > limit) fail('Preview file is not a bounded regular file');
    const buffer = Buffer.alloc(limit + 1);
    let count = 0;
    while (count < buffer.length) {
      const result = await handle.read(buffer, count, buffer.length - count, null);
      if (!result.bytesRead) break;
      count += result.bytesRead;
    }
    if (count > limit) fail('Preview file exceeds its size limit');
    return buffer.subarray(0, count);
  } finally { await handle.close(); }
}

export function createPreviewService(ctx, run, spawnProcess = spawn) {
  const games = new Map(), busy = new Set();
  let disposed = false;
  async function permission(sessionID, action, resources, source) {
    await ctx.permission.assert({ sessionID, action, resources, save: resources, ...(source ? { source } : {}) });
  }
  function snapshot(entry) {
    const value = { state: entry.state, pid: entry.child?.pid, code: entry.code, signal: entry.signal,
      version: entry.version, diagnostics: entry.diagnostics,
      evidence: { graphical_correctness: false, playtested: false } };
    // OpenCode validates RPC values before JSON serialization. A running process
    // has no exit code/signal yet; omit unknown fields, preserving real 0/null.
    return Object.fromEntries(Object.entries(value).filter(([, item]) => item !== undefined));
  }
  async function stop(entry) {
    if (!entry || entry.state !== 'running') return;
    entry.child.kill('SIGTERM');
    await Promise.race([entry.closed, new Promise(resolve => { const timer = setTimeout(resolve, 1500); timer.unref?.(); })]);
    if (entry.state === 'running') {
      entry.child.kill('SIGKILL');
      await Promise.race([entry.closed, new Promise(resolve => { const timer = setTimeout(resolve, 1500); timer.unref?.(); })]);
    }
    if (entry.state === 'running') fail('Could not confirm the preview process stopped; no replacement was launched');
  }
  async function versionOf(binary, root, signal) {
    return await new Promise((resolve, reject) => {
      let output = '', settled = false;
      const child = spawnProcess(binary, ['--version'], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
      const done = (error) => {
        if (settled) return;
        settled = true; clearTimeout(timer); signal?.removeEventListener('abort', abort);
        if (error) { child.kill('SIGKILL'); reject(error); } else resolve(output.trim());
      };
      const abort = () => done(new PreviewFailure('Preview launch cancelled'));
      const timer = setTimeout(() => done(new PreviewFailure('Godot version check timed out')), 5000);
      for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => {
        output += chunk.toString(); if (output.length > 4096) done(new PreviewFailure('Unexpected Godot version output'));
      });
      child.on('error', () => done(new PreviewFailure('Cannot start Godot; configure .daydream/preview.json with the project engine')));
      child.on('close', code => done(code ? new PreviewFailure('Godot version check failed') : undefined));
      signal?.addEventListener('abort', abort, { once: true });
      if (signal?.aborted) abort();
    });
  }
  async function launch(root, sessionID, signal, source, scene) {
    if (busy.has(root)) fail('A preview action is already in progress for this project');
    busy.add(root);
    try {
      const previous = games.get(root);
      if (previous?.state === 'running') {
        if (previous.scene !== scene) fail('Another preview is running. Stop it with /preview stop before running this scene');
        return { ok: true, ...snapshot(previous), already_running: true };
      }
      const scenePath = scene ? await projectPath(root, scene) : undefined;
      if (scenePath && path.extname(scenePath) !== '.tscn') fail('Choose a project .tscn scene to preview');
      await permission(sessionID, 'read', [path.join(root, 'project.godot'), path.join(root, '.daydream/preview.json'), ...(scenePath ? [scenePath] : [])], source);
      const project = (await read(await projectPath(root, 'project.godot'))).toString();
      if (!scenePath && !/^\s*run\/main_scene\s*=\s*"[^"\n]+"/m.test(project)) fail('No configured main scene in project.godot; choose one in Godot first');
      if (scenePath) await read(scenePath, 4 * 1024 * 1024);
      let settings = {};
      try { settings = JSON.parse((await read(await projectPath(root, '.daydream/preview.json'), 16384)).toString()); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (!settings || typeof settings !== 'object' || Array.isArray(settings) || Object.keys(settings).some(key => !['godot', 'version'].includes(key))) fail('Preview configuration supports only godot and version');
      let binary = settings.godot ?? process.env.GODOT_BIN ?? 'godot';
      if (typeof binary !== 'string' || !binary || /[\x00-\x1f]/.test(binary) || binary.startsWith('-')) fail('Godot must be an executable path, not flags or a shell command');
      if (binary.includes('/') && !path.isAbsolute(binary)) binary = path.resolve(root, binary);
      if (settings.version !== undefined && (typeof settings.version !== 'string' || !/^4\.\d+\.\d+(?:\.[A-Za-z0-9_.-]+)?$/.test(settings.version))) fail('version must be an explicit Godot 4 version, such as 4.7.2');
      // Includes --version: even a project-configured executable can execute code.
      await permission(sessionID, 'daydream.preview.game', [root, binary, ...(scenePath ? [scenePath] : [])], source);
      await permission(sessionID, 'edit', [path.join(root, '**')], source);
      if (signal?.aborted || disposed) fail('Preview launch cancelled');
      const version = await versionOf(binary, root, signal);
      if (!/^4\.\d+\.\d+(?:\.|$)/.test(version)) fail('Expected Godot 4; configure the engine used by this project');
      if (settings.version && version !== settings.version && !version.startsWith(settings.version + '.')) fail(`Godot version mismatch: expected ${settings.version}, found ${version}`);
      if (signal?.aborted || disposed) fail('Preview launch cancelled');
      const entry = { state: 'starting', diagnostics: '', version, scene };
      const child = spawnProcess(binary, ['--path', root, ...(scenePath ? ['res://' + path.relative(root, scenePath)] : [])], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
      entry.child = child;
      entry.closed = new Promise(resolve => child.once('close', (code, exitSignal) => {
        entry.state = code === 0 || exitSignal ? 'exited' : 'failed'; entry.code = code; entry.signal = exitSignal; resolve();
      }));
      for (const stream of [child.stdout, child.stderr]) stream.on('data', chunk => {
        entry.diagnostics = (entry.diagnostics + chunk.toString().replace(/\x1b\[[0-?]*[ -/]*[@-~]/g, '').replace(/[\x00-\x08\x0b-\x1f\x7f]/g, '')).slice(-8192);
      });
      child.on('error', () => { entry.state = 'failed'; entry.diagnostics = 'Could not launch the Godot preview process'; });
      games.set(root, entry);
      await new Promise((resolve, reject) => { child.once('spawn', resolve); child.once('error', reject); });
      if (entry.state === 'starting') entry.state = 'running';
      // Catch immediate startup failures without waiting for the game to finish.
      await new Promise(resolve => setTimeout(resolve, 250));
      if (signal?.aborted || disposed) { await stop(entry); fail('Preview launch cancelled'); }
      return { ok: entry.state !== 'failed', ...snapshot(entry) };
    } finally { busy.delete(root); }
  }
  async function assets(root, input, signal, source) {
    const request = { op: 'assets.list', input: { history: input.history ?? false } };
    const check = value => { if (!value.ok) fail(value.error.message); return value; };
    const prepared = check(await run(root, { action: 'prepare', ...request }, signal));
    await permission(input.sessionID, 'read', prepared.access.reads, source);
    let authorized = { reads: prepared.access.reads, writes: [] };
    const resolved = check(await run(root, { action: 'resolve', ...request, authorized }, signal));
    const extra = resolved.access.reads.filter(file => !authorized.reads.includes(file));
    if (extra.length) await permission(input.sessionID, 'read', extra, source);
    authorized = { reads: resolved.access.reads, writes: [] };
    const result = check(await run(root, { action: 'call', ...request, authorized }, signal));
    return { ok: true, ...result.result };
  }
  async function document(root, bundle, signal) {
    const directory = await projectPath(root, bundle);
    const manifest = JSON.parse((await read(await projectPath(root, path.join(directory, 'manifest.json')))).toString());
    const kind = manifest.kind === 'sprite' ? 'sprite' : manifest.kind === 'sprite_animation' ? 'animation' : manifest.kind === 'tileset' ? 'tileset' : fail('Not a Daydream sprite/animation/tileset revision');
    const input = { bundle }, op = `${kind}.inspect`;
    const prepared = await run(root, { action: 'prepare', op, input }, signal);
    if (!prepared.ok) fail(prepared.error.message);
    const result = await run(root, { action: 'call', op, input, authorized: { reads: prepared.access.reads, writes: [] } }, signal);
    if (!result.ok) fail(result.error.message);
    // Bind the document to the exact revision that was validated, even if files change.
    const manifestHash = createHash('sha256').update(await read(path.join(directory, 'manifest.json'))).digest('hex');
    if (manifestHash !== result.result.revision_hash) fail('Revision changed during preview; try again');
    const review = await run(root, { action: 'call', op: 'review.inspect', input: { bundle, kind }, authorized: { reads: prepared.access.reads, writes: [] } }, signal);
    if (!review.ok) fail(review.error.message);
    if (review.result.revision_hash !== result.result.revision_hash) fail('Revision changed during preview; try again');
    let total = 0;
    const image = async (name, scale = 1, motion) => {
      const data = await read(await projectPath(root, path.join(directory, name)), 8 * 1024 * 1024);
      total += data.length;
      if (total > 10 * 1024 * 1024) fail('Preview images exceed the 10 MiB viewer limit');
      if (createHash('sha256').update(data).digest('hex') !== manifest.files[name]) fail('Preview image changed during review');
      const width = data.readUInt32BE(16);
      const playback = motion ? ` data-motion data-loop="${motion.loop}" data-duration-ms="${motion.duration_ms}" data-visual-frames="${motion.visual_frames}"` : '';
      return scale ? `<div class="viewport"><img class="art"${playback} style="--pixel-width:${width / scale}px" alt="${escape(name)}" src="data:image/png;base64,${data.toString('base64')}"></div>`
        : `<img class="reference" alt="${escape(name)}" src="data:image/png;base64,${data.toString('base64')}">`;
    };
    let body = '';
    if (kind === 'sprite') body = `<h3>Artwork · ${result.result.width} × ${result.result.height} pixels</h3>${await image('sprite.png')}`;
    else if (kind === 'tileset') {
      body = `<h3>Layout</h3>${await image('layout.png')}<h3>Tiles</h3>${await image('atlas.png')}<details><summary>Numbered tiles and seam checks</summary><p>Boundary mismatches: ${result.result.seams.mismatch_count}. Yellow: solid geometry; cyan: one-way geometry.</p>${await image('preview.png', 0)}</details>`;
      if (result.result.collision_preview) {
        const geometry = result.result.tiles.map(tile => ({ id: tile.id, solid: tile.solid, polygons: tile.collisions ?? null }));
        body += `<h3>Collision coverage (not artwork)</h3>${await image('collisions.png')}<p>Raster overlays are approximate; exact coordinates use top-left tile pixels on a half-pixel grid. One-way polygons block from local above; omitted one_way is false and omitted margin is 1. A legacy solid:true with polygons:null is the unchanged full-tile rectangle; solid:false with polygons:null has no collisions. No shapes are inferred from alpha.</p><details><summary>Exact collision geometry</summary><pre>${escape(JSON.stringify(geometry, null, 2))}</pre></details>`;
      }
    }
    else for (const clip of result.result.previews) {
      body += `<section><h3>${escape(clip.animation)}</h3><p class="version-meta">Saved playback: ${clip.loop ? 'loops' : 'plays once'}</p>${await image(path.basename(clip.motion), 4, clip)}<details><summary>Contact sheet (reference layout)</summary>${await image(path.basename(clip.contact_sheet), 0)}</details></section>`;
    }
    return { body, revision_hash: result.result.revision_hash, kind, manifest_kind: manifest.kind, id: result.result.name, bundle,
      parent_revision_hash: manifest.provenance?.parent_revision_hash, state: review.result.state,
      notes: review.result.feedback?.notes ?? [], name: manifest.provenance?.display_name ?? result.result.name };
  }
  async function assetDocument(root, input, signal, source) {
    const current = await document(root, input.bundle, signal);
    const history = [];
    let notice = '', isLatest = true;
    try {
      const catalog = await assets(root, { ...input, history: true }, signal, source);
      const selected = olderVersions(current, catalog);
      isLatest = selected.isLatest;
      if (selected.limited) notice = 'Comparison shows up to eight earlier versions within the preview size limit. Use Show older revisions in /assets for more history.';
      let bytes = Buffer.byteLength(current.body + feedbackHTML(current.notes));
      for (const item of selected.previous) {
        if (signal?.aborted || disposed) fail('Comparison cancelled');
        let viewed = item;
        if (!item.error) {
          try {
            viewed = { ...item, ...await document(root, item.bundle, signal) };
            if (viewed.revision_hash !== item.revision_hash) fail('Earlier version changed while opening comparison; reopen the preview');
            const size = Buffer.byteLength(viewed.body + feedbackHTML(viewed.notes));
            if (bytes + size > VIEWER_BODY_LIMIT) fail('This earlier version exceeds the comparison size limit. Open it separately with Show older revisions in /assets.');
            bytes += size;
          } catch (error) { viewed = { ...item, error: `Cannot preview this earlier version: ${error.message}` }; }
        }
        history.push(viewed);
      }
    } catch (error) { notice = `Version comparison unavailable: ${error.message}`; }
    if (signal?.aborted || disposed) fail('Comparison cancelled');
    return { ok: true, html: assetViewer(current, history, { notice, isLatest }), revision_hash: current.revision_hash,
      kind: current.kind, name: current.name };
  }
  return {
    async call(input, { signal, source } = {}) {
      if (disposed) fail('Preview service is closed');
      if (!input || typeof input.sessionID !== 'string' || !['game', 'status', 'stop', 'assets', 'asset', 'gallery'].includes(input.action)) fail('Invalid preview request');
      const session = await ctx.session.get({ sessionID: input.sessionID });
      const root = await realpath(session.location.directory);
      if (ctx.location && root !== await realpath(ctx.location.directory)) fail('Preview session belongs to a different plugin location');
      if (input.action === 'game') return await launch(root, input.sessionID, signal, source, input.scene);
      if (input.action === 'status') {
        if (games.has(root)) await permission(input.sessionID, 'daydream.preview.status', [root], source);
        return { ok: true, ...(games.has(root) ? snapshot(games.get(root)) : { state: 'not_running' }) };
      }
      if (input.action === 'stop') {
        if (busy.has(root)) fail('A preview launch is in progress; wait before stopping');
        await permission(input.sessionID, 'daydream.preview.stop', [root], source);
        busy.add(root);
        try { await stop(games.get(root)); return { ok: true, state: 'stopped' }; }
        finally { busy.delete(root); }
      }
      if (input.action === 'assets') return await assets(root, input, signal, source);
      // Inspection never runs project code or opens browsers on the server.
      await permission(input.sessionID, 'read', [path.join(root, '**')], source);
      if (input.action === 'gallery') {
        const catalog = await assets(root, input, signal, source);
        let cards = '', bytes = 0;
        for (const item of catalog.assets.slice(0, 12)) {
          if (signal?.aborted || disposed) fail('Gallery cancelled');
          try {
            const viewed = await document(root, item.bundle, signal);
            const thumbnail = viewed.body.match(/<img[^>]+src="data:image\/png;base64,[^"]+"[^>]*>/)?.[0] ?? '';
            bytes += Buffer.byteLength(thumbnail);
            if (bytes > 8 * 1024 * 1024) break;
            cards += `<section><h2>${escape(item.name)}</h2><p>${escape(item.state)} · ${escape(item.kind)}</p>${thumbnail}<p>${escape(item.bundle)}</p><small>${escape(viewed.revision_hash)}</small></section>`;
          } catch (error) { cards += `<section><h2>${escape(item.name)}</h2><p>Cannot preview: ${escape(error.message)}</p></section>`; }
        }
        return { ok: true, html: `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><title>Daydream assets</title><style>body{background:#20232b;color:white;font:16px system-ui;margin:2rem}main{display:flex;flex-wrap:wrap;gap:2rem}section{width:300px;overflow-wrap:anywhere}img{max-width:280px;max-height:240px;object-fit:contain;image-rendering:pixelated}</style><h1>Your assets</h1><p>Up to 12 current candidates. Select an asset in OpenCode to review and decide. Imported means files exist, not proof they are placed in gameplay. Animation thumbnails are not motion review.</p><main>${cards}</main>` };
      }
      return await assetDocument(root, input, signal, source);
    },
    async dispose() { disposed = true; await Promise.all([...games.values()].map(stop)); },
  };
}
