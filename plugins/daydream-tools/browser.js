import { spawn } from 'node:child_process';
import { mkdtemp, writeFile, rm } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

// The browser runs on the TUI client, not on a possibly remote OpenCode server.
export function createBrowser(spawnProcess = spawn, temporaryRoot = os.tmpdir()) {
  const directories = new Set();
  let closed = false;
  return {
    async open(html) {
      if (closed) throw new Error('Preview browser is closed');
      if (typeof html !== 'string' || Buffer.byteLength(html) > 16 * 1024 * 1024) throw new Error('Invalid or oversized preview document');
      if (!['linux', 'darwin'].includes(process.platform)) throw new Error('Browser preview currently supports Linux and macOS');
      if (directories.size >= 20) throw new Error('Preview viewer limit reached; restart the TUI to clean up its temporary viewers');
      const directory = await mkdtemp(path.join(temporaryRoot, 'daydream-preview-'));
      if (closed) { await rm(directory, { recursive: true, force: true }); throw new Error('Preview browser is closed'); }
      directories.add(directory);
      const file = path.join(directory, 'preview.html');
      await writeFile(file, html, { mode: 0o600, flag: 'wx' });
      await new Promise((resolve, reject) => {
        const child = spawnProcess(process.platform === 'darwin' ? 'open' : 'xdg-open', [pathToFileURL(file).href], { stdio: 'ignore', shell: false });
        let settled = false;
        const finish = error => {
          if (settled) return;
          settled = true; clearTimeout(timer);
          error ? reject(error) : resolve();
        };
        // Some desktop openers remain alive for the browser's entire lifetime.
        // Detect immediate failures, but do not wait for or kill the user's viewer.
        const timer = setTimeout(() => { child.unref?.(); finish(); }, 500);
        child.once('error', () => finish(new Error('Cannot open browser; check the system default browser')));
        child.once('close', code => finish(code === 0 ? undefined : new Error('Browser opener failed')));
      });
      return file;
    },
    async dispose() {
      closed = true;
      await Promise.all([...directories].map(directory => rm(directory, { recursive: true, force: true })));
      directories.clear();
    },
  };
}
