export const stateLabel = value => ({ draft: 'Draft', unreviewed: 'Draft', approved: 'Approved', changes_requested: 'Needs changes', imported: 'Imported', modified: 'Modified outside Daydream' }[value] ?? value);
export const assetStep = (number, title) => `Step ${number} of 5 — ${title}`;
const kindLabel = kind => ({ sprite: 'Static sprite', sprite_animation: 'Animation', animation: 'Animation', tileset: 'Tileset' }[kind] ?? kind);
const savedTime = new Intl.DateTimeFormat('en', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', timeZone: 'UTC', timeZoneName: 'short' });
function savedLabel(value) {
  const date = new Date(value / 1e6);
  return Number.isFinite(value) && Number.isFinite(date.getTime()) ? `Saved ${savedTime.format(date)}` : 'Saved time unavailable';
}

export async function pickAsset(context, list, sessionID, browser, { readOnly = false } = {}) {
  let history = false;
  for (;;) {
    const result = await list({ sessionID, action: 'assets', history });
    if (!result?.ok) throw new Error(result?.error?.message ?? 'Could not list assets');
    const canCreate = !readOnly && context.client?.session?.prompt;
    const selection = context.ui.dialog.select({ title: history ? 'Asset history — newest saved first' : readOnly ? 'Choose artwork — latest candidates' : 'Your assets — latest candidates',
      current: result.assets?.[0]?.bundle ?? (canCreate ? '\0create' : '\0help'), options: [
      ...(canCreate ? [{ title: 'Describe a new asset…', value: '\0create', category: '1 · Create', description: 'Tell Daydream what to make; then review its candidate' }] : []),
      ...(result.assets ?? []).map(asset => ({ title: `${asset.is_latest === true || (!history && asset.is_latest !== false) ? 'Latest' : asset.is_latest === false ? 'Older' : 'Revision'} · ${kindLabel(asset.kind)} — ${asset.name ?? asset.bundle}`, value: asset.bundle,
        category: readOnly ? 'Artwork — newest saved first' : history ? '2 · Version history — newest saved first' : '2 · Review a latest candidate — newest saved first',
        description: `${savedLabel(asset.modified_at)} · ${stateLabel(asset.state ?? 'draft')}${asset.older_revisions ? ` · ${asset.older_revisions} older` : ''}` })),
      ...(browser ? [{ title: 'Open thumbnail overview', value: '\0gallery', category: 'Browse and history', description: 'See the available artwork before choosing a candidate' }] : []),
      { title: history ? 'Back to current assets' : 'Show older revisions', value: '\0history', category: 'Browse and history', description: history ? 'Show only the latest candidate of each asset type' : 'Compare saved times; Latest marks the newest of each asset type' },
      { title: 'View imported assets', value: '\0imported', category: 'Browse and history', description: 'See files already added and their current status' },
      { title: 'Workflow steps', value: '\0help', category: 'Help and advanced', description: 'Create → review/revise → approve → add/update → preview' },
      { title: 'Enter a revision path (advanced)', value: '\0manual', category: 'Help and advanced' },
      { title: 'Close', value: '\0close', category: 'Finish' },
    ] });
    // The standard narrow picker clips type, saved time and review state.
    context.ui.dialog.set?.({ size: 'large' });
    const selected = await selection;
    if (!selected || selected === '\0close') return;
    if (selected === '\0history') { history = !history; continue; }
    if (selected === '\0imported') {
      const id = await context.ui.dialog.select({ title: 'Imported resource files', options: [
        ...(result.active ?? []).map(asset => ({ title: `${kindLabel(asset.kind)} — ${asset.name}`, value: asset.id, description: `${stateLabel(asset.state)} · ${asset.scene}` })),
        { title: 'Back', value: '\0back' },
      ] });
      const asset = (result.active ?? []).find(asset => asset.id === id);
      if (asset) await context.ui.dialog.alert({ title: asset.name, message: `${stateLabel(asset.state)}\nScene: ${asset.scene}\nSource revision: ${asset.bundle ?? 'not recorded by this older import'}\n${asset.modified_files?.length ? '\nProtected modified/missing files:\n' + asset.modified_files.join('\n') : '\nManaged outputs match their recorded hashes.'}\n\nImported files are not proof of gameplay placement. Review a new candidate to update this asset; manually edited files require a separate copy.` });
      continue;
    }
    if (selected === '\0gallery') {
      if (await context.ui.dialog.confirm({ title: 'Open asset overview?', message: 'Open validated thumbnails in your browser? No asset is approved, imported or changed.', label: { confirm: 'Open overview', cancel: 'Cancel' } })) {
        const gallery = await list({ sessionID, action: 'gallery' });
        if (!gallery?.ok) throw new Error(gallery?.error?.message ?? 'Could not prepare overview');
        await browser.open(gallery.html);
      }
      continue;
    }
    if (selected === '\0help') {
      await context.ui.dialog.alert({ title: 'Your asset workflow — in order', message: 'In /assets:\n\n1. Create: choose Describe a new asset… and follow progress in chat.\n2. Review: select the candidate and inspect its preview. Compare earlier versions if available. To revise, Request changes → save feedback → Make revised version, then review the result.\n3. Approve: choose Approve artwork when satisfied. For Reviewer label, enter your name or user.\n4. Add/update: choose Add or update in project, choose a copy or an existing managed asset, review the plan, then confirm applying it.\n5. Preview: choose Preview this scene. If the asset is already placed in your game, use /preview game to check it there. A new copy still needs placement.\n\nResume at the step that matches your candidate’s status. Daydream carries its name and saved feedback for you.' });
      continue;
    }
    if (selected === '\0create') {
      if (readOnly) return;
      const brief = await context.ui.dialog.prompt({ title: assetStep(1, 'Describe your asset'), placeholder: 'A mossy stone floor called Moonlight Floor, 16×16 pixel tiles' });
      if (!brief?.trim()) continue;
      if (brief.length > 4000) { await context.ui.dialog.alert({ title: 'Shorten the asset brief', message: 'Please keep this request under 4000 characters.' }); continue; }
      const route = context.ui.router.current();
      if (route.type !== 'session' || route.sessionID !== sessionID) throw new Error('Session changed; describe the asset again in its intended project');
      await context.client.session.prompt({ sessionID, text: `Create a staged asset for review in this project using the available shared Daydream tools and project instructions. Use a friendly name and omit output for automatic hidden revision storage. Clarify any missing art-direction requirements. Do not approve or import it; I will review the candidate in /assets.\n\nMy asset brief:\n${brief.trim()}` });
      context.ui.toast.show({ title: 'Step 1 — request sent', message: 'Follow progress in chat. Next: open /assets, select the new candidate, and review its preview (step 2).', variant: 'success' });
      return;
    }
    if (selected === '\0manual') return await context.ui.dialog.prompt({ title: 'Revision folder', placeholder: 'art/tiles/hut-floor-v5' });
    return selected;
  }
}
