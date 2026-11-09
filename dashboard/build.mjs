import { build } from 'esbuild';
import { mkdir, writeFile, readFile, readdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const root = path.dirname(fileURLToPath(import.meta.url));
const output = path.resolve(root, '../plugins/daydream-tools/dashboard-dist');
await mkdir(output, { recursive: true });
const result = await build({ entryPoints: [path.join(root, 'src/main.tsx')], bundle: true, minify: true, format: 'esm',
  target: ['es2022'], outfile: path.join(output, 'app.js'), metafile: true,
  loader: { '.woff2': 'dataurl', '.woff': 'dataurl' },
  define: { 'process.env.NODE_ENV': '"production"' }, legalComments: 'none',
  banner: { js: '/*! Bundled third-party license notices: see licenses.txt. */' } });
await writeFile(path.join(output, 'index.html'), '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Daydream · Asset collection</title><link rel="stylesheet" href="/app.css"></head><body><div id="root"></div><script type="module" src="/app.js"></script></body></html>');
// Include the actual license texts of all packages used by the production bundle.
const packages = new Set(Object.keys(result.metafile.inputs).flatMap(file => {
  const match = file.replaceAll('\\', '/').match(/node_modules\/((?:@[^/]+\/)?[^/]+)/);
  return match ? [match[1]] : [];
}));
let notices = 'Third-party notices for the bundled Daydream dashboard UI.\n\n';
const missing = [];
for (const name of [...packages].sort()) {
  const directory = path.join(root, 'node_modules', name);
  const info = JSON.parse(await readFile(path.join(directory, 'package.json'), 'utf8'));
  const files = (await readdir(directory)).filter(file => /^licen[sc]e(?:\.|$)/i.test(file));
  notices += `\n--- ${name}@${info.version} (${info.license}) ---\n`;
  if (!files.length) {
    try { notices += await readFile(path.join(root, 'third-party', name.replaceAll('/', '__') + '.LICENSE'), 'utf8') + '\n'; }
    catch { missing.push(name); }
  }
  for (const file of files) notices += await readFile(path.join(directory, file), 'utf8') + '\n';
}
if (missing.length) throw new Error('Missing license notices for ' + missing.join(', '));
await writeFile(path.join(output, 'licenses.txt'), notices.replace(/\r\n?/g, '\n').split('\n').map(line => line.replace(/[\t ]+$/, '')).join('\n').trimEnd() + '\n');
console.log('Built offline dashboard and third-party notices:', output);
