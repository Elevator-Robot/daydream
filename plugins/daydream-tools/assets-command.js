import { pickAsset, stateLabel } from './asset-picker.js';

function explain(error) {
  const message = String(error.message ?? error);
  if (/input\.name/.test(message)) return 'Please use an asset name of 1–120 characters. Spaces and capitals are fine; Daydream handles filenames.';
  if (/input\.reviewer/.test(message)) return 'Please use a short reviewer label, such as your name (up to 120 characters).';
  if (/input\.feedback/.test(message)) return 'Please describe the requested changes in 1–4000 characters.';
  return message;
}

export function assetsCommand(context, call, listAssets, browser) {
  let busy = false;
  return {
    id: 'daydream.assets', title: 'Your assets', group: 'Daydream', palette: true,
    slash: { name: 'assets', arguments: true },
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
        if (!bundle) bundle = await pickAsset(context, listAssets, sessionID, browser);
        if (!bundle) return;
        if (!await context.ui.dialog.confirm({ title: 'Open asset for review?', message: 'Open an exact-revision browser viewer. Inspect the artwork, watch animation motion, or check tile layouts/collisions. Opening alone does not approve anything.', label: { confirm: 'Open review', cancel: 'Cancel' } })) return;
        const opened = await invoke({ action: 'open', bundle });
        ticket = opened.ticket;
        await browser.open(opened.html); // Never offer approval if opening the viewer failed.
        let status = opened.status;
        for (;;) {
          const decision = await context.ui.dialog.select({ title: `${opened.name} — ${stateLabel(status.state)}`, current: 'cancel', options: [
            { title: 'Cancel / finish review', value: 'cancel', description: 'No additional decision or import' },
            { title: 'Open preview again', value: 'preview' },
            { title: 'Approve artwork', value: 'approve', disabled: status.state === 'changes_requested', description: 'Approve this exact revision only; nothing is imported' },
            { title: 'Request changes', value: 'changes', description: 'Retain feedback; block further import of this revision' },
            { title: 'Add or update in project', value: 'plan', disabled: status.state !== 'approved', description: status.state === 'approved' ? 'Choose a safe add/update plan; nothing changes until confirmed' : 'Approve the reviewed artwork first' },
          ] });
          if (!decision || decision === 'cancel') return;
          if (decision === 'preview') { await browser.open(opened.html); continue; }
          if (decision === 'plan') {
            try {
            const choices = await invoke({ action: 'options', ticket });
            if (choices.initialized === false) {
              if (!await context.ui.dialog.confirm({ title: 'Set up asset tracking for this project?', message: 'Daydream needs small .daydream metadata files to track imports safely. Existing files are preserved. This does not add artwork or change gameplay.', label: { confirm: 'Set up tracking', cancel: 'Back' } })) continue;
              await invoke({ action: 'setup', ticket });
            }
            const mode = await context.ui.dialog.select({ title: 'What should happen to this asset?', current: 'copy', options: [
              { title: 'Add a separate copy', value: 'copy', description: 'Safe default: filenames chosen automatically; existing scenes stay unchanged' },
              ...choices.targets.map(target => ({ title: `Update ${target.name}`, value: 'update:' + target.id, disabled: !target.can_update || target.same_revision,
                description: !target.can_update ? 'Manual edits detected — protected. Add a separate copy instead' : target.same_revision ? 'This exact revision is already imported' : 'Keep current paths/references; archive previous bytes first' })),
              { title: 'Back to review', value: 'cancel' },
            ] });
            if (!mode || mode === 'cancel') continue;
            const target = mode.startsWith('update:') ? choices.targets.find(target => target.id === mode.slice(7)) : undefined;
            const options = target ? { strategy: 'update', target: target.id } : { strategy: 'copy' };
            if (!target) {
              const naming = await context.ui.dialog.select({ title: 'Name for your asset', current: 'keep', options: [
                { title: `Keep “${opened.name}”`, value: 'keep', description: 'Daydream picks available file-safe names for you' },
                { title: 'Give it another friendly name', value: 'rename', description: 'Spaces and capitals are welcome' },
                { title: 'Back', value: 'cancel' },
              ] });
              if (!naming || naming === 'cancel') continue;
              if (naming === 'rename') {
                const name = await context.ui.dialog.prompt({ title: 'Asset name (spaces and capitals are fine)', placeholder: 'Potion Shop Floor' });
                if (!name?.trim()) continue;
                options.name = name.trim();
              }
            }
            if (opened.kind === 'tileset' && target) options.layout = target.layout;
            else if (opened.kind === 'tileset') {
              const layout = await context.ui.dialog.select({ title: 'Tile layout import mode', current: 'editor', options: [
                { title: 'Editor-visible cells (script-free scene)', value: 'editor', description: 'Automatically uses this project’s Godot; prepares the scene in an isolated fixture' },
                { title: 'Runtime layout companion (legacy)', value: 'runtime', description: 'No Godot serialization; cells populate only when the scene runs' },
                { title: 'Cancel', value: 'cancel' },
              ] });
              if (!layout || layout === 'cancel') continue;
              options.layout = layout;
              if (layout === 'editor') {
                if (!await context.ui.dialog.confirm({ title: 'Prepare editor-visible layout?', message: 'Daydream will detect this project’s Godot and check its version. It prepares the scene in a disposable project without running your game code. Nothing is imported until you review and apply the plan.', label: { confirm: 'Prepare layout', cancel: 'Cancel' } })) continue;
              }
            }
            const result = await invoke({ action: 'plan', ticket, ...options });
            let apply = false;
            for (;;) {
              const choice = await context.ui.dialog.select({ title: result.plan.summary ?? `Add ${opened.name} to this project`, current: 'back', options: [
                { title: target ? 'Apply this update' : 'Add this asset', value: 'apply', description: result.plan.history ? 'Recovery snapshot retained; current paths stay stable' : 'Creates separate resource files, not gameplay placement' },
                { title: 'Show technical details', value: 'details', description: 'Exact paths, revision, plan hash and history location' },
                { title: 'Keep staged / back', value: 'back' },
              ] });
              if (choice !== 'details') { apply = choice === 'apply'; break; }
              await context.ui.dialog.alert({ title: 'Exact plan details', message: `Friendly name: ${result.plan.display_name ?? opened.name}\nFile ID: ${result.plan.asset_name ?? ''}\nRevision: ${opened.revision_hash}\nPlan: ${result.plan.plan_hash}\n\nCreate:\n${result.plan.create.join('\n')}\n\nReplace managed files:\n${(result.plan.replace ?? []).join('\n')}\n\nUpdate: ${result.plan.update}\nRecovery snapshot: ${result.plan.history ?? 'not needed for a new asset'}${result.plan.serialization ? '\nGodot serializer: ' + result.plan.serialization.version : ''}` });
            }
            if (!apply || !await context.ui.dialog.confirm({ title: target ? 'Update this managed asset?' : 'Add this approved asset?', message: result.plan.summary ?? 'Apply the reviewed plan? A changed revision or plan will be refused.', label: { confirm: target ? 'Update asset' : 'Add asset', cancel: 'Keep staged' } })) continue;
            const imported = await invoke({ action: 'import', ticket });
            ticket = undefined;
            context.ui.toast.show({ title: 'Daydream assets', message: target ? 'Managed asset updated; previous bytes are retained in history.' : 'Asset added as separate files. It has not been placed into gameplay.', variant: 'success' });
            const next = await context.ui.dialog.select({ title: 'Asset ready — what next?', current: 'done', options: [
              { title: 'How to open it in Godot', value: 'open' },
              { title: 'Preview this scene', value: 'preview', description: 'Runs project code; separate permission required' },
              { title: 'Done', value: 'done' },
            ] });
            const scene = imported.result?.scene ?? result.plan.scene;
            if (next === 'open') await context.ui.dialog.alert({ title: 'Open in Godot', message: `In Godot’s FileSystem dock, open:\n${scene ?? 'the scene shown in plan details'}\n\nEditor-visible tile layouts can be painted immediately. F6 previews this standalone scene. Instancing it in your game remains a separate deliberate change.` });
            if (next === 'preview' && scene && await context.ui.dialog.confirm({ title: 'Run the imported scene?', message: 'This runs your project’s code/autoloads in graphical Godot and may write generated data. It does not change the main scene.', label: { confirm: 'Run scene', cancel: 'Cancel' } })) {
              const result = await listAssets({ sessionID, action: 'game', scene });
              if (!result?.ok) throw new Error(result?.error?.message ?? 'Scene preview failed; use /preview status for launch diagnostics');
              context.ui.toast.show({ title: 'Scene preview', message: `Preview ${result.state ?? 'requested'}. Use /preview status for diagnostics and /preview stop to stop it.`, variant: 'success' });
            }
            return;
            } catch (error) {
              await context.ui.dialog.alert({ title: ticket ? 'Let’s adjust the plan' : 'Asset saved — next action failed', message: explain(error) + (ticket ? '\n\nYour review is still open. Choose a separate copy if the existing asset has manual edits or a different file layout. No update is retried automatically.' : '\n\nThe asset was already saved. Nothing was retried; use /assets to inspect it.') });
              if (!ticket) return;
              continue;
            }
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
        const message = explain(error);
        context.ui.toast.show({ title: 'Your assets', message, variant: 'error', duration: 10000 });
        await context.ui.dialog.alert({ title: 'Asset action stopped — details', message: message + '\n\nNo decision or import was automatically retried. If approval was already confirmed, it remains recorded. Choose Add a separate copy for protected or incompatible assets; never delete user work to bypass a refusal.' });
      } finally {
        if (ticket) { try { await invoke({ action: 'cancel', ticket }); } catch { /* Expired/unloaded ticket: no decision is retried. */ } }
        busy = false;
      }
    },
  };
}
