export function reviewCommand(context, call, listAssets, browser) {
  let busy = false;
  return {
    id: 'daydream.review', title: 'Review and approve an asset', group: 'Daydream', palette: true,
    slash: { name: 'asset-review', aliases: ['daydream-review'], arguments: true },
    enabled: () => context.ui.router.current().type === 'session',
    async run(argument = '') {
      if (busy) return;
      const route = context.ui.router.current();
      if (route.type !== 'session') return;
      busy = true;
      const sessionID = route.sessionID;
      let ticket;
      const invoke = async input => {
        const current = context.ui.router.current();
        if (input.action !== 'cancel' && (current.type !== 'session' || current.sessionID !== sessionID)) throw new Error('Active session changed; open the review again in its original session');
        const result = await call({ sessionID, ...input });
        if (!result?.ok) throw new Error(result?.error?.message ?? 'Review failed');
        return result;
      };
      try {
        let bundle = String(argument).trim();
        if (!bundle) {
          const result = await listAssets({ sessionID, action: 'assets' });
          bundle = await context.ui.dialog.select({ title: 'Review asset revision', options: [
            ...result.assets.map(asset => ({ title: asset.bundle, description: asset.kind, value: asset.bundle })),
            { title: 'Enter revision path…', value: '\0manual' },
          ] });
          if (bundle === '\0manual') bundle = await context.ui.dialog.prompt({ title: 'Revision bundle path', placeholder: 'art/sprites/slime-v1' });
        }
        if (!bundle) return;
        if (!await context.ui.dialog.confirm({ title: 'Open asset for review?', message: 'Open an exact-revision browser viewer. Inspect the artwork, watch animation motion, or check tile layouts/collisions. Opening alone does not approve anything.', label: { confirm: 'Open review', cancel: 'Cancel' } })) return;
        const opened = await invoke({ action: 'open', bundle });
        ticket = opened.ticket;
        await browser.open(opened.html); // Never offer approval if opening the viewer failed.
        let status = opened.status;
        for (;;) {
          const decision = await context.ui.dialog.select({ title: `${opened.name} — ${status.state} — ${opened.revision_hash.slice(0, 12)}`, current: 'cancel', options: [
            { title: 'Cancel / finish review', value: 'cancel', description: 'No additional decision or import' },
            { title: 'Open preview again', value: 'preview' },
            { title: 'Approve exact revision', value: 'approve', disabled: status.state === 'changes_requested', description: 'Records approval only; does not import' },
            { title: 'Request changes', value: 'changes', description: 'Retain feedback; block further import of this revision' },
            { title: 'Review import plan', value: 'plan', disabled: status.state !== 'approved', description: 'Separate destination/content plan and apply confirmation' },
          ] });
          if (!decision || decision === 'cancel') return;
          if (decision === 'preview') { await browser.open(opened.html); continue; }
          if (decision === 'plan') {
            const mode = await context.ui.dialog.select({ title: 'Import destination', current: 'defaults', options: [
              { title: 'Use project defaults', value: 'defaults' },
              { title: 'Choose a new asset name', value: 'name' },
              { title: 'Choose another destination directory', value: 'destination' },
              { title: 'Choose both name and destination', value: 'both' },
              { title: 'Cancel', value: 'cancel' },
            ] });
            if (!mode || mode === 'cancel') continue;
            const options = {};
            if (mode === 'name' || mode === 'both') {
              const name = await context.ui.dialog.prompt({ title: 'Import asset name', placeholder: opened.name });
              if (!name?.trim()) continue;
              options.name = name.trim();
            }
            if (mode === 'destination' || mode === 'both') {
              const destination = await context.ui.dialog.prompt({ title: 'Project-relative destination directory', placeholder: 'assets/sprites or assets/tilesets' });
              if (!destination?.trim()) continue;
              options.destination = destination.trim();
            }
            const result = await invoke({ action: 'plan', ticket, ...options });
            await context.ui.dialog.alert({ title: 'Review exact import plan', message: `Revision: ${opened.revision_hash}\nPlan: ${result.plan.plan_hash}\n\nCreate:\n${result.plan.create.join('\n')}\n\nUpdate: ${result.plan.update}\n\nExisting assets and scenes will not be replaced. Approval is separate from import.` });
            if (!await context.ui.dialog.confirm({ title: 'Apply this reviewed import?', message: 'Write only the displayed outputs and update the asset index? A changed revision, plan or configuration requires a new review.', label: { confirm: 'Apply import', cancel: 'Keep staged' } })) continue;
            await invoke({ action: 'import', ticket });
            ticket = undefined;
            context.ui.toast.show({ title: 'Daydream review', message: 'Exact reviewed revision imported. Existing game scenes were not modified.', variant: 'success' });
            return;
          }
          let feedback;
          if (decision === 'changes') {
            feedback = await context.ui.dialog.prompt({ title: 'What needs changing?', placeholder: 'Describe the revision you want (up to 4000 characters)' });
            if (!feedback?.trim()) continue;
          }
          const reviewer = await context.ui.dialog.prompt({ title: 'Reviewer label', placeholder: 'Your name or review label (not authenticated identity)' });
          if (!reviewer?.trim()) continue;
          const message = `Asset: ${opened.name}\nRevision: ${opened.revision_hash}\nReviewer: ${reviewer.trim()}\n\n${decision === 'approve'
            ? 'I reviewed this exact artwork, watched its motion if animated, and checked layout/collision data if a tileset. Record approval only; do not import.'
            : 'Record these requested changes and block further import of this revision:\n' + feedback.trim()}`;
          if (!await context.ui.dialog.confirm({ title: decision === 'approve' ? 'Approve exact revision?' : 'Record requested changes?', message, label: { confirm: decision === 'approve' ? 'Approve revision' : 'Request changes', cancel: 'Cancel' } })) continue;
          const result = await invoke({ action: decision, ticket, reviewer: reviewer.trim(), ...(feedback ? { feedback: feedback.trim() } : {}) });
          status = result.status;
          context.ui.toast.show({ title: 'Daydream review', message: decision === 'approve' ? 'Approval recorded. Nothing imported; review the import plan separately.' : 'Feedback saved. Create a fresh revision to address it; no generation was started.', variant: 'success' });
          if (decision === 'changes') return;
        }
      } catch (error) {
        context.ui.toast.show({ title: 'Daydream review', message: String(error.message ?? error), variant: 'error', duration: 10000 });
      } finally {
        if (ticket) { try { await invoke({ action: 'cancel', ticket }); } catch { /* Expired/unloaded ticket: no decision is retried. */ } }
        busy = false;
      }
    },
  };
}
