import { createHash } from 'node:crypto';

export const escapeHTML = value => String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));
export const HISTORY_LIMIT = 8;
export const VIEWER_BODY_LIMIT = 14 * 1024 * 1024;

// Presentation over the shared catalog. Prefer recorded ancestry over file times;
// never follow a path supplied by provenance or mistake another asset for history.
export function olderVersions(current, catalog) {
  const family = catalog.assets.filter(item => item.id === current.id && item.kind === current.manifest_kind);
  const byHash = new Map();
  for (const item of family) if (!byHash.has(item.revision_hash)) byHash.set(item.revision_hash, item);
  const selected = family.find(item => item.revision_hash === current.revision_hash);
  const seen = new Set([current.revision_hash]), previous = [];
  let parent = current.parent_revision_hash;
  while (parent && !seen.has(parent) && previous.length < HISTORY_LIMIT) {
    seen.add(parent);
    const item = byHash.get(parent);
    if (!item) {
      previous.push({ revision_hash: parent, error: 'This earlier version could not be found or its metadata is invalid. Use Show older revisions in /assets to inspect the available history.' });
      break;
    }
    previous.push(item);
    parent = item.parent_revision_hash;
  }
  for (const item of family) {
    if (selected && item.modified_at < selected.modified_at && !seen.has(item.revision_hash)) {
      seen.add(item.revision_hash);
      previous.push(item);
    }
  }
  return { previous: previous.slice(0, HISTORY_LIMIT), limited: previous.length > HISTORY_LIMIT || Boolean(parent && !seen.has(parent)) || catalog.truncated,
    isLatest: !family.length || family[0].revision_hash === current.revision_hash };
}

const stateLabel = state => ({ changes_requested: 'Needs changes', unreviewed: 'Draft', approved: 'Approved' }[state] ?? 'Draft');
const saved = value => Number.isFinite(value) ? new Date(value / 1e6).toISOString().replace('T', ' ').replace(/\.\d+Z$/, ' UTC') : '';
export function feedbackHTML(notes) {
  return `<section class="feedback"><h3>Saved feedback for this version</h3>${notes?.length
    ? '<ol>' + notes.map(note => `<li><p class="note">${escapeHTML(note.feedback)}</p><small>${escapeHTML(note.reviewer)} · ${escapeHTML(note.reviewed_at)}</small></li>`).join('') + '</ol>'
    : '<p>No feedback saved for this version.</p>'}</section>`;
}

// This script only switches already embedded views. Its CSP hash permits this
// fixed code, not asset names, notes, inline handlers, network or filesystem reads.
export const viewerScript = `const compare = document.getElementById('compare');
const older = document.getElementById('older-version');
const history = document.getElementById('history-panel');
const panels = document.getElementById('panels');
const motion = new Map([...document.querySelectorAll('img[data-motion]')].map(img => [img, { source: img.src }]));
function replayMotion() {
  for (const [img, entry] of motion) {
    if (!img.getClientRects().length) continue;
    if (entry.url) URL.revokeObjectURL(entry.url);
    const bytes = Uint8Array.from(atob(entry.source.split(',')[1]), ch => ch.charCodeAt(0));
    entry.url = URL.createObjectURL(new Blob([bytes], { type: 'image/png' }));
    img.src = entry.url;
  }
}
function selectOlder() {
  for (const pane of document.querySelectorAll('[data-history-index]')) pane.hidden = pane.dataset.historyIndex !== older.value;
  replayMotion();
}
if (compare) {
  compare.addEventListener('toggle', () => {
    history.hidden = !compare.open;
    panels.classList.toggle('comparing', compare.open);
    replayMotion();
  });
  older.addEventListener('change', selectOlder);
  selectOlder();
}
document.getElementById('replay-motion')?.addEventListener('click', replayMotion);
window.addEventListener('pagehide', () => { for (const entry of motion.values()) if (entry.url) URL.revokeObjectURL(entry.url); });
document.getElementById('zoom').addEventListener('change', event => {
  const zoom = Number(event.target.value);
  if ([1, 2, 4, 8].includes(zoom)) document.documentElement.style.setProperty('--zoom', zoom);
});`;

export function assetViewer(current, history = [], { notice = '', isLatest = true } = {}) {
  const esc = escapeHTML;
  const scriptHash = createHash('sha256').update(viewerScript).digest('base64');
  const label = isLatest && current.state === 'unreviewed' ? 'New candidate' : 'Selected version';
  const details = item => `<details class="technical"><summary>Version details</summary><code>${esc(item.revision_hash)}</code>${item.bundle ? `<p>${esc(item.bundle)}</p>` : ''}</details>`;
  const oldPane = (item, index) => `<div data-history-index="${index}"${index ? ' hidden' : ''}>
    <h2>${index ? 'Older version' : 'Previous version'}</h2><p class="version-meta">${esc(saved(item.modified_at))}${item.state ? ' · ' + stateLabel(item.state) : ''}</p>
    ${item.error ? `<p role="status">${esc(item.error)}</p>` : item.body + feedbackHTML(item.notes)}${details(item)}</div>`;
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data: blob:; style-src 'unsafe-inline'; script-src 'sha256-${scriptHash}'; base-uri 'none'; form-action 'none'">
<title>${esc(current.name)} — Daydream preview</title><style>
:root{color-scheme:dark;--zoom:4}*{box-sizing:border-box}body{font:16px/1.5 system-ui;background:#171b24;color:#edf1f7;margin:0;padding:2rem;max-width:1600px;margin-inline:auto}h1{margin:0;font-size:1.8rem}h2{margin:0;font-size:1.25rem}h3{font-size:1rem}p{margin:.6rem 0}small,.version-meta{color:#b6c1d2}.eyebrow{color:#adbeff;font-weight:700;letter-spacing:.08em;text-transform:uppercase;font-size:.8rem}.guidance{border-left:3px solid #9dacf9;padding-left:1rem}.controls{display:flex;gap:1.5rem;align-items:start;flex-wrap:wrap;margin:1.5rem 0}select,summary{cursor:pointer}select{font:inherit;background:#262e40;color:#edf1f7;border:1px solid #61708d;border-radius:.4rem;padding:.4rem;max-width:100%}summary{color:#c8d2ff;font-weight:600}details label{display:block;margin-top:.75rem}.panels{display:grid;grid-template-columns:minmax(0,1fr);gap:1.25rem}.panels.comparing{grid-template-columns:repeat(2,minmax(0,1fr))}.panel{min-width:0;border:1px solid #424e65;background:#202735;border-radius:.75rem;padding:1.25rem}.candidate{border-color:#8b9cff}.viewport{overflow:auto;background:#171b24;border-radius:.4rem;padding:1rem;min-height:180px;max-height:500px;margin:.75rem 0}.art{display:block;image-rendering:pixelated;width:calc(var(--pixel-width)*var(--zoom));max-width:none;height:auto;background:repeating-conic-gradient(#b0b3ba 0% 25%,#dddfe4 0% 50%) 0/16px 16px}.reference{image-rendering:pixelated;max-width:100%}.note{white-space:pre-wrap;overflow-wrap:anywhere}.feedback{border-top:1px solid #424e65;margin-top:1.25rem}.feedback li{padding-bottom:.5rem}code,pre,.technical{overflow-wrap:anywhere}pre{white-space:pre-wrap}.technical{margin-top:1rem;font-size:.85rem}.notice{color:#ffdda1}[hidden]{display:none!important}footer{margin-top:1.5rem;color:#b6c1d2}@media(max-width:700px){body{padding:1rem}.panels.comparing{grid-template-columns:minmax(0,1fr)}}
button{font:inherit;cursor:pointer;background:#354568;color:#edf1f7;border:1px solid #91a5dc;border-radius:.4rem;padding:.4rem .8rem}
.workflow{display:flex;flex-wrap:wrap;gap:.4rem 2rem;padding-left:1.3rem;margin:1rem 0;color:#b6c1d2;font-size:.9rem}.workflow [aria-current=step]{color:#c8d2ff;font-weight:700}
</style></head><body data-reviewed-revision="${esc(current.revision_hash)}"><header><p class="eyebrow">Daydream · artwork review</p><h1>${esc(current.name)}</h1>
<nav aria-label="Asset workflow"><ol class="workflow"><li>Create</li><li aria-current="step">Review / revise</li><li>Approve</li><li>Add / update</li><li>Preview</li></ol></nav>
<p class="guidance">Preview only — opening this viewer does not approve or import. Return to <strong>/assets</strong> to decide about the <strong>${label.toLowerCase()}</strong>. Comparing older versions never changes the candidate under review.</p></header>
<div class="controls">${history.length ? `<details id="compare"><summary>Compare with previous version</summary><label for="older-version">Older version</label><select id="older-version">${history.map((item, index) => `<option value="${index}">${index ? 'Older version ' + (index + 1) : 'Previous version'}${item.modified_at ? ' · ' + esc(saved(item.modified_at)) : ''}${item.error ? ' · unavailable' : ''}</option>`).join('')}</select></details>` : '<p>No older version is available for comparison.</p>'}
<label for="zoom">Artwork scale <select id="zoom"><option value="1">1×</option><option value="2">2×</option><option value="4" selected>4×</option><option value="8">8×</option></select></label>${current.kind === 'animation' ? '<button id="replay-motion" type="button">Replay motion</button>' : ''}</div>
${notice ? `<p class="notice" role="status">${esc(notice)}</p>` : ''}<noscript>Enable JavaScript to compare embedded versions and change scale. The selected candidate is shown below.</noscript>
<main id="panels" class="panels">${history.length ? `<aside id="history-panel" class="panel" aria-label="Earlier versions, reference only" hidden>${history.map(oldPane).join('')}</aside>` : ''}
<article class="panel candidate" aria-label="Candidate under review"><h2>${label}</h2><p class="version-meta">${stateLabel(current.state)} · Candidate under review</p>${current.body}${feedbackHTML(current.notes)}${details(current)}</article></main>
<footer>Both sides use the same artwork pixel scale. Scroll large images; narrow windows stack the versions. Feedback is a snapshot from when this preview opened.${current.kind === 'animation' ? ' Clips use their own timing; Replay motion restarts both visible versions.' : ''}</footer>
<script>${viewerScript}</script></body></html>`;
}
