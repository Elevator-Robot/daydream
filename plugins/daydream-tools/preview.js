import { spawn } from "node:child_process";
import { lstat, open, readdir, realpath } from "node:fs/promises";
import { constants } from "node:fs";
import path from "node:path";
import { createHash } from "node:crypto";

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
    return { state: entry.state, pid: entry.child?.pid, code: entry.code, signal: entry.signal,
      version: entry.version, diagnostics: entry.diagnostics,
      evidence: { graphical_correctness: false, playtested: false } };
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
  async function launch(root, sessionID, signal, source) {
    if (busy.has(root)) fail('A preview action is already in progress for this project');
    busy.add(root);
    try {
      const previous = games.get(root);
      if (previous?.state === 'running') return { ok: true, ...snapshot(previous), already_running: true };
      await permission(sessionID, 'read', [path.join(root, 'project.godot'), path.join(root, '.daydream/preview.json')], source);
      const project = (await read(await projectPath(root, 'project.godot'))).toString();
      if (!/^\s*run\/main_scene\s*=\s*"[^"\n]+"/m.test(project)) fail('No configured main scene in project.godot; choose one in Godot first');
      let settings = {};
      try { settings = JSON.parse((await read(await projectPath(root, '.daydream/preview.json'), 16384)).toString()); }
      catch (error) { if (error.code !== 'ENOENT') throw error; }
      if (!settings || typeof settings !== 'object' || Array.isArray(settings) || Object.keys(settings).some(key => !['godot', 'version'].includes(key))) fail('Preview configuration supports only godot and version');
      let binary = settings.godot ?? process.env.GODOT_BIN ?? 'godot';
      if (typeof binary !== 'string' || !binary || /[\x00-\x1f]/.test(binary) || binary.startsWith('-')) fail('Godot must be an executable path, not flags or a shell command');
      if (binary.includes('/') && !path.isAbsolute(binary)) binary = path.resolve(root, binary);
      if (settings.version !== undefined && (typeof settings.version !== 'string' || !/^4\.\d+\.\d+(?:\.[A-Za-z0-9_.-]+)?$/.test(settings.version))) fail('version must be an explicit Godot 4 version, such as 4.7.2');
      // Includes --version: even a project-configured executable can execute code.
      await permission(sessionID, 'daydream.preview.game', [root, binary], source);
      await permission(sessionID, 'edit', [path.join(root, '**')], source);
      if (signal?.aborted || disposed) fail('Preview launch cancelled');
      const version = await versionOf(binary, root, signal);
      if (!/^4\.\d+\.\d+(?:\.|$)/.test(version)) fail('Expected Godot 4; configure the engine used by this project');
      if (settings.version && version !== settings.version && !version.startsWith(settings.version + '.')) fail(`Godot version mismatch: expected ${settings.version}, found ${version}`);
      if (signal?.aborted || disposed) fail('Preview launch cancelled');
      const entry = { state: 'starting', diagnostics: '', version };
      const child = spawnProcess(binary, ['--path', root], { cwd: root, stdio: ['ignore', 'pipe', 'pipe'], shell: false });
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
  async function assets(root) {
    let source = 'art';
    try {
      const config = JSON.parse((await read(await projectPath(root, '.daydream/config.json'))).toString());
      source = config.paths?.sources ?? source;
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    const start = await projectPath(root, source), found = [], pending = [start];
    let count = 0;
    while (pending.length && count < 1000 && found.length < 100) {
      const directory = pending.shift(); count++;
      let entries;
      try { entries = await readdir(directory, { withFileTypes: true }); }
      catch (error) { if (error.code === 'ENOENT') continue; throw error; }
      if (entries.some(entry => entry.name === 'manifest.json' && entry.isFile())) {
        try {
          const manifest = JSON.parse((await read(await projectPath(root, path.join(directory, 'manifest.json')))).toString());
          if (['sprite', 'sprite_animation', 'tileset'].includes(manifest.kind)) found.push({ bundle: path.relative(root, directory), kind: manifest.kind });
        } catch { /* Invalid candidates are not selectable; explicit paths report errors. */ }
      }
      for (const entry of entries.slice(0, 1000)) if (entry.isDirectory() && !entry.name.startsWith('.') && pending.length < 1000) pending.push(path.join(directory, entry.name));
    }
    return { ok: true, assets: found, truncated: pending.length > 0, sources_dir: source };
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
    let total = 0;
    const image = async (name) => {
      const data = await read(await projectPath(root, path.join(directory, name)), 8 * 1024 * 1024);
      total += data.length;
      if (total > 10 * 1024 * 1024) fail('Preview images exceed the 10 MiB viewer limit');
      if (createHash('sha256').update(data).digest('hex') !== manifest.files[name]) fail('Preview image changed during review');
      return `<img alt="${escape(name)}" src="data:image/png;base64,${data.toString('base64')}">`;
    };
    let body = '';
    if (kind === 'sprite') body = await image('preview.png');
    else if (kind === 'tileset') body = `<p>Boundary mismatches: ${result.result.seams.mismatch_count}. Yellow outlines: full-tile collisions. Human visual review required.</p><h2>Tiles</h2>${await image('preview.png')}<h2>Layout</h2>${await image('layout.png')}`;
    else for (const clip of result.result.previews) {
      body += `<section><h2>${escape(clip.animation)}</h2>${await image(path.basename(clip.motion))}<h3>Contact sheet</h3>${await image(path.basename(clip.contact_sheet))}</section>`;
    }
    const html = `<!doctype html><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:; style-src 'unsafe-inline'"><title>Daydream preview</title><style>body{font:16px system-ui;background:#20232b;color:#eee;margin:2rem}img{image-rendering:pixelated;max-width:100%;background:repeating-conic-gradient(#bbb 0% 25%,#ddd 0% 50%) 0/16px 16px}code{overflow-wrap:anywhere}</style><h1>${escape(result.result.name)}</h1><p>Revision: <code>${escape(result.result.revision_hash)}</code></p><p>Preview only — opening this viewer does not approve or import.</p>${body}`;
    return { ok: true, html, revision_hash: result.result.revision_hash, kind, name: result.result.name };
  }
  return {
    async call(input, { signal, source } = {}) {
      if (disposed) fail('Preview service is closed');
      if (!input || typeof input.sessionID !== 'string' || !['game', 'status', 'stop', 'assets', 'asset'].includes(input.action)) fail('Invalid preview request');
      const session = await ctx.session.get({ sessionID: input.sessionID });
      const root = await realpath(session.location.directory);
      if (ctx.location && root !== await realpath(ctx.location.directory)) fail('Preview session belongs to a different plugin location');
      if (input.action === 'game') return await launch(root, input.sessionID, signal, source);
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
      // Listing and inspection never run project code or open browsers on the server.
      await permission(input.sessionID, 'read', [path.join(root, '**')], source);
      return input.action === 'assets' ? await assets(root) : await document(root, input.bundle, signal);
    },
    async dispose() { disposed = true; await Promise.all([...games.values()].map(stop)); },
  };
}
