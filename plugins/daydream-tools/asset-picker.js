export const stateLabel = value => ({ draft: 'Draft', unreviewed: 'Draft', approved: 'Approved', changes_requested: 'Needs changes', imported: 'Imported', modified: 'Modified outside Daydream' }[value] ?? value);

export async function pickAsset(context, list, sessionID, browser, { readOnly = false } = {}) {
  let history = false;
  for (;;) {
    const result = await list({ sessionID, action: 'assets', history });
    if (!result?.ok) throw new Error(result?.error?.message ?? 'Could not list assets');
    const selected = await context.ui.dialog.select({ title: history ? 'Asset history — select a revision' : 'Your assets — current candidates', options: [
      ...(result.assets ?? []).map(asset => ({ title: asset.name ?? asset.bundle, value: asset.bundle,
        description: `${stateLabel(asset.state ?? 'draft')} · ${asset.kind}${asset.older_revisions ? ` · ${asset.older_revisions} older revisions` : ''} · ${asset.bundle}` })),
      { title: history ? 'Back to current assets' : 'Show older revisions', value: '\0history', description: 'History is retained; nothing is deleted' },
      { title: 'View imported assets', value: '\0imported', description: 'Stable scene paths and manual-edit status; no changes' },
      ...(browser ? [{ title: 'Open thumbnail overview', value: '\0gallery', description: 'Up to 12 validated current candidates in your browser' }] : []),
      { title: 'Help: create an asset', value: '\0help', description: 'Ask Daydream using ordinary words; it manages filenames and revisions' },
      ...(!readOnly && context.client?.session?.prompt ? [{ title: 'Describe a new asset…', value: '\0create', description: 'Send a creation request to the current agent; review before approval/import' }] : []),
      { title: 'Enter a revision path (advanced)', value: '\0manual' },
      { title: 'Close', value: '\0close' },
    ] });
    if (!selected || selected === '\0close') return;
    if (selected === '\0history') { history = !history; continue; }
    if (selected === '\0imported') {
      const id = await context.ui.dialog.select({ title: 'Imported resource files', options: [
        ...(result.active ?? []).map(asset => ({ title: asset.name, value: asset.id, description: `${stateLabel(asset.state)} · ${asset.scene}` })),
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
      await context.ui.dialog.alert({ title: 'Create → review → add to game', message: 'Ask Daydream: “Create a small pixel-art floor named Potion Shop Floor. Show me a candidate before importing.”\n\nNew tool-generated revisions are kept under .daydream/revisions automatically. You review the picture here, approve it, then separately choose Add a copy or Update an unchanged managed asset.\n\nImported means resource files exist, not that a scene has been placed into gameplay. Existing game maps are never silently rewritten.' });
      continue;
    }
    if (selected === '\0create') {
      if (readOnly) return;
      const brief = await context.ui.dialog.prompt({ title: 'Describe your asset (sends a model request)', placeholder: 'A mossy stone floor called Moonlight Floor, 16×16 pixel tiles' });
      if (!brief?.trim()) continue;
      if (brief.length > 4000) { await context.ui.dialog.alert({ title: 'Shorten the asset brief', message: 'Please keep this request under 4000 characters.' }); continue; }
      const route = context.ui.router.current();
      if (route.type !== 'session' || route.sessionID !== sessionID) throw new Error('Session changed; describe the asset again in its intended project');
      await context.client.session.prompt({ sessionID, text: `Create a staged asset for review in this project using the available shared Daydream tools and project instructions. Use a friendly name and omit output for automatic hidden revision storage. Clarify any missing art-direction requirements. Do not approve or import it; I will review the candidate in /assets.\n\nMy asset brief:\n${brief.trim()}` });
      context.ui.toast.show({ title: 'Asset request sent', message: 'Daydream will prepare a candidate. Return to /assets to review it; nothing is automatically approved or imported.', variant: 'success' });
      return;
    }
    if (selected === '\0manual') return await context.ui.dialog.prompt({ title: 'Revision folder', placeholder: 'art/tiles/hut-floor-v5' });
    return selected;
  }
}
