import { createServer } from 'node:http';
import { randomBytes, timingSafeEqual } from 'node:crypto';
import { readFile } from 'node:fs/promises';

const STATIC = new Map([
  ['/', ['index.html', 'text/html; charset=utf-8']],
  ['/app.js', ['app.js', 'text/javascript; charset=utf-8']],
  ['/app.css', ['app.css', 'text/css; charset=utf-8']],
  ['/licenses.txt', ['licenses.txt', 'text/plain; charset=utf-8']],
]);
const CSP = "default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; font-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'";

// Client-side, session-owned loopback transport. No OpenCode credentials enter
// the browser, and browser asset IDs resolve only through a permissioned catalog.
export async function createDashboardBridge({ sessionID, project, call, staticDirectory = new URL('./dashboard-dist/', import.meta.url) }) {
  const token = randomBytes(32).toString('hex');
  const assets = new Map(), requests = new Set(), staticFiles = new Map(), sockets = new Set();
  for (const [route, [file, type]] of STATIC) staticFiles.set(route, { bytes: await readFile(new URL(file, staticDirectory)), type });
  let origin, host, closed = false, active = 0, catalogGeneration = 0;
  const send = (response, status, value) => {
    if (response.destroyed) return;
    response.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8' });
    response.end(JSON.stringify(value));
  };
  const server = createServer(async (request, response) => {
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('Content-Security-Policy', CSP);
    response.setHeader('Referrer-Policy', 'no-referrer');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    response.setHeader('Cross-Origin-Resource-Policy', 'same-origin');
    if (closed || request.headers.host !== host || (request.headers.origin && request.headers.origin !== origin) || request.headers['sec-fetch-site'] === 'cross-site') return send(response, 403, { error: 'Dashboard origin rejected' });
    if (request.method !== 'GET') return send(response, 405, { error: 'This dashboard is read-only' });
    let url;
    try { url = new URL(request.url, origin); }
    catch { return send(response, 400, { error: 'Invalid dashboard URL' }); }
    if (url.origin !== origin) return send(response, 403, { error: 'Dashboard origin rejected' });
    const file = staticFiles.get(url.pathname);
    if (file && !url.search) { response.writeHead(200, { 'Content-Type': file.type }); response.end(file.bytes); return; }
    const supplied = request.headers.authorization ?? '';
    const expected = 'Bearer ' + token;
    if (typeof supplied !== 'string' || Buffer.byteLength(supplied) !== Buffer.byteLength(expected) || !timingSafeEqual(Buffer.from(supplied), Buffer.from(expected))) return send(response, 401, { error: 'Reopen the dashboard from /assets to reconnect.' });
    if (!['/api/catalog', '/api/inspect', '/api/media'].includes(url.pathname)) return send(response, 404, { error: 'Unknown dashboard route' });
    if (active >= 8) return send(response, 429, { error: 'Dashboard is busy. Refresh again in a moment.' });
    const controller = new AbortController(); requests.add(controller); active++;
    response.on('close', () => { if (!response.writableEnded) controller.abort(); });
    try {
      const action = url.pathname.slice(5);
      let input = { sessionID, project, action };
      let selected;
      const generation = action === 'catalog' ? ++catalogGeneration : catalogGeneration;
      if (action !== 'catalog') {
        const entry = assets.get(url.searchParams.get('id'));
        if (!entry) return send(response, 404, { error: 'This asset is not in the current collection. Refresh first.' });
        selected = entry;
        input = { ...input, path: entry.path, kind: entry.kind,
          ...(entry.sprite_resources?.length ? { resources: entry.sprite_resources } : {}),
          ...(entry.revision_hash ? { revision_hash: entry.revision_hash } : {}),
          ...(action === 'media' ? { image: url.searchParams.get('image') ?? 'thumbnail' } : {}) };
      }
      const result = await call(input, { signal: controller.signal });
      if (!result?.ok) throw new Error(result?.error?.message ?? 'Could not read the project');
      if (closed || controller.signal.aborted) return;
      if (selected?.kind === 'image' && generation === catalogGeneration && /^[0-9a-f]{64}$/.test(result.revision_hash ?? '')) {
        const current = assets.get(selected.id);
        if (current?.revision_hash && current.revision_hash !== result.revision_hash) throw new Error('This image changed while loading. Refresh the collection to inspect it again.');
        if (current) assets.set(selected.id, { ...current, revision_hash: result.revision_hash });
      }
      if (action === 'catalog' && generation === catalogGeneration) {
        assets.clear();
        for (const entry of result.assets) assets.set(entry.id, entry);
      }
      send(response, 200, result);
    } catch (error) { send(response, 400, { error: String(error.message ?? error) }); }
    finally { active--; requests.delete(controller); }
  });
  server.requestTimeout = 130000;
  server.headersTimeout = 10000;
  server.maxHeadersCount = 30;
  server.on('connection', socket => { sockets.add(socket); socket.once('close', () => sockets.delete(socket)); });
  await new Promise((resolve, reject) => { server.once('error', reject); server.listen(0, '127.0.0.1', resolve); });
  host = '127.0.0.1:' + server.address().port;
  origin = 'http://' + host;
  return {
    url: origin + '/#token=' + token,
    async dispose() {
      closed = true; assets.clear();
      for (const request of requests) request.abort();
      for (const socket of sockets) socket.destroy();
      await new Promise(resolve => server.close(resolve));
    },
  };
}

export function createDashboardManager(call, openURL) {
  const bridges = new Map();
  let closed = false;
  return {
    async open(sessionID, project) {
      if (closed) throw new Error('Dashboard connection closed');
      const key = JSON.stringify([sessionID, project]);
      if (!bridges.has(key)) {
        if (bridges.size >= 4) throw new Error('Four project dashboards are already open; restart Daydream to close their connections.');
        const starting = createDashboardBridge({ sessionID, project, call });
        bridges.set(key, starting);
        try { await starting; } catch (error) { bridges.delete(key); throw error; }
      }
      const bridge = await bridges.get(key);
      if (closed) throw new Error('Dashboard connection closed');
      await openURL(bridge.url);
      return bridge.url;
    },
    async dispose() {
      closed = true;
      await Promise.allSettled([...bridges.values()].map(async starting => (await starting).dispose()));
      bridges.clear();
    },
  };
}
