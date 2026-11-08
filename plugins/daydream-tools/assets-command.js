import { assetStep, pickAsset, stateLabel } from './asset-picker.js';

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
      const checkSession = () => {
        const current = context.ui.router.current();
        if (current.type !== 'session' || current.sessionID !== sessionID) throw new Error('Active session changed; open the review again in its original session');
      };
      const invoke = async input => {
        if (input.action !== 'cancel') checkSession();
        const result = await call({ sessionID, ...input });
        if (!result?.ok) throw new Error(result?.error?.message ?? 'Review failed');
        return result;
      };
      try {
        let bundle = String(argument).trim();
        if (!bundle) bundle = await pickAsset(context, listAssets, sessionID, browser);
        if (!bundle) return;
        if (!await context.ui.dialog.confirm({ title: assetStep(2, 'Open the review preview?'), message: '1. Inspect the artwork in your browser. Watch animation motion or check tile layouts/collisions.\n2. Use Compare with previous version if earlier artwork is available.\n3. Return here to request changes or approve this candidate.\n\nOpening the preview records no decision.', label: { confirm: 'Open review', cancel: 'Cancel' } })) return;
        const opened = await invoke({ action: 'open', bundle });
        ticket = opened.ticket;
        await browser.open(opened.html); // Never offer approval if opening the viewer failed.
        let status = opened.status;
        for (;;) {
          const notes = status.feedback?.notes ?? (status.feedback ? [status.feedback] : []);
          const approved = status.state === 'approved';
          const decision = await context.ui.dialog.select({ title: `${assetStep(approved ? 4 : 2, approved ? 'Add or update' : 'Review or revise')} · ${opened.name} (${stateLabel(status.state)})`, current: notes.length ? 'revise' : approved ? 'plan' : 'preview', options: [
            { title: 'Open preview again', value: 'preview', category: '2 · Review or revise', description: 'Inspect or compare the artwork before deciding' },
            ...(notes.length ? [{ title: 'Read saved feedback', value: 'feedback', category: '2 · Review or revise', description: `${notes.length} note${notes.length === 1 ? '' : 's'} saved for this version` }] : []),
            { title: notes.length ? 'Add more feedback' : 'Request changes', value: 'changes', category: '2 · Review or revise', description: notes.length ? 'Clarify the requested changes; earlier notes are kept' : 'Save what needs improving; then choose Make revised version' },
            ...(notes.length ? [{ title: 'Make revised version', value: 'revise', category: '2 · Review or revise', disabled: !context.client?.session?.prompt, description: 'Next: send this asset and saved notes to Daydream, then review the new candidate' }] : []),
            { title: 'Approve artwork', value: 'approve', category: '3 · Approve', disabled: status.state === 'changes_requested' || approved, description: approved ? 'Completed for this version — continue to step 4' : 'When satisfied, approve this exact version; adding it comes next' },
            { title: 'Add or update in project', value: 'plan', category: '4 · Add or update', disabled: !approved, description: approved ? 'Next: choose where it goes, review the plan, then confirm' : 'Available after step 3: Approve artwork' },
            { title: 'Cancel / finish review', value: 'cancel', category: 'Finish for now', description: 'Saved feedback and approval are kept; resume later in /assets' },
          ] });
          if (!decision || decision === 'cancel') return;
          if (decision === 'preview') { await browser.open(opened.html); continue; }
          if (decision === 'revise') {
            if (!context.client?.session?.prompt) throw new Error('This OpenCode client cannot send revision requests; update OpenCode and reopen /assets');
            const request = await invoke({ action: 'revise', ticket });
            checkSession(); // The active session may have changed during reads/permissions.
            try {
              await context.client.session.prompt({ sessionID, text: request.text });
            } catch (error) {
              throw new Error('Could not confirm the revision request: ' + explain(error) + '\nCheck the chat before trying again; the request may already have arrived.');
            }
            context.ui.toast.show({ title: 'Revision request sent', message: 'Next: follow progress in chat, then reopen /assets to review the new candidate (step 2). The selected asset and all notes were included.', variant: 'success' });
            return;
          }
          if (decision === 'feedback') {
            await context.ui.dialog.alert({ title: `Saved feedback — ${opened.name}`, message: notes.map((note, index) => `${index + 1}. ${note.reviewer} — ${note.reviewed_at}\n${note.feedback}`).join('\n\n') + '\n\nChoose Make revised version to have Daydream use these notes. This version cannot be approved or imported while changes are requested.' });
            continue;
          }
          if (decision === 'plan') {
            try {
            const choices = await invoke({ action: 'options', ticket });
            if (choices.initialized === false) {
              if (!await context.ui.dialog.confirm({ title: 'Set up asset tracking for this project?', message: 'Daydream needs small .daydream metadata files to track imports safely. Existing files are preserved. This does not add artwork or change gameplay.', label: { confirm: 'Set up tracking', cancel: 'Back' } })) continue;
              await invoke({ action: 'setup', ticket });
            }
            const mode = await context.ui.dialog.select({ title: assetStep(4, 'Choose copy or update'), current: 'copy', options: [
              { title: 'Add a separate copy', value: 'copy', description: 'Safe default: filenames chosen automatically; existing scenes stay unchanged' },
              ...choices.targets.map(target => ({ title: `Update ${target.name}`, value: 'update:' + target.id, disabled: !target.can_update || target.same_revision,
                description: !target.can_update ? 'Manual edits detected — protected. Add a separate copy instead' : target.same_revision ? 'This exact revision is already imported' : 'Keep current paths/references; archive previous bytes first' })),
              { title: 'Back to review', value: 'cancel' },
            ] });
            if (!mode || mode === 'cancel') continue;
            const target = mode.startsWith('update:') ? choices.targets.find(target => target.id === mode.slice(7)) : undefined;
            const options = target ? { strategy: 'update', target: target.id } : { strategy: 'copy' };
            if (!target) {
              const naming = await context.ui.dialog.select({ title: assetStep(4, 'Name the copy'), current: 'keep', options: [
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
              const layout = await context.ui.dialog.select({ title: assetStep(4, 'Choose the tile layout'), current: 'editor', options: [
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
              const choice = await context.ui.dialog.select({ title: assetStep(4, result.plan.summary ?? `Review the plan for ${opened.name}`), current: 'back', options: [
                { title: target ? 'Apply this update' : 'Add this asset', value: 'apply', description: result.plan.history ? 'Confirm the reviewed update; previous files are retained in history' : 'Confirm adding the reviewed files; scene placement is separate' },
                { title: 'Show technical details', value: 'details', description: 'Optional: exact paths, revision, plan hash and history location' },
                { title: 'Keep staged / back', value: 'back' },
              ] });
              if (choice !== 'details') { apply = choice === 'apply'; break; }
              await context.ui.dialog.alert({ title: 'Exact plan details', message: `Friendly name: ${result.plan.display_name ?? opened.name}\nFile ID: ${result.plan.asset_name ?? ''}\nRevision: ${opened.revision_hash}\nPlan: ${result.plan.plan_hash}\n\nCreate:\n${result.plan.create.join('\n')}\n\nReplace managed files:\n${(result.plan.replace ?? []).join('\n')}\n\nUpdate: ${result.plan.update}\nRecovery snapshot: ${result.plan.history ?? 'not needed for a new asset'}${result.plan.serialization ? '\nGodot serializer: ' + result.plan.serialization.version : ''}` });
            }
            if (!apply || !await context.ui.dialog.confirm({ title: assetStep(4, target ? 'Confirm this update?' : 'Confirm adding this asset?'), message: result.plan.summary ?? 'Apply the reviewed plan? A changed revision or plan will be refused.', label: { confirm: target ? 'Update asset' : 'Add asset', cancel: 'Keep staged' } })) continue;
            const imported = await invoke({ action: 'import', ticket });
            ticket = undefined;
            context.ui.toast.show({ title: 'Step 4 complete', message: target ? 'Managed asset updated. Next: preview the scene, or use /preview game if your game already uses it.' : 'Asset files added. Next: preview the standalone scene; placing this copy in your game is separate.', variant: 'success' });
            const next = await context.ui.dialog.select({ title: assetStep(5, 'Preview the result'), current: 'preview', options: [
              { title: 'Preview this scene', value: 'preview', description: 'Next: run the standalone asset scene after launch confirmation' },
              { title: 'How to open it in Godot', value: 'open', description: 'Open, inspect and playtest manually; see how to continue into your game' },
              { title: 'Done', value: 'done' },
            ] });
            const scene = imported.result?.scene ?? result.plan.scene;
            if (next === 'open') await context.ui.dialog.alert({ title: assetStep(5, 'Open and playtest'), message: `1. In Godot’s FileSystem dock, open:\n${scene ?? 'the scene shown in plan details'}\n2. Inspect the asset; editor-visible tile layouts can be painted here. Press F6 to preview this standalone scene.\n3. ${target ? 'If your game already uses this asset, run /preview game to check the update there.' : 'When this copy is ready, ask Daydream to place it in the intended game scene. Then run /preview game to test it in context.'}` });
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
            feedback = await context.ui.dialog.prompt({ title: notes.length ? 'What else should change?' : 'What needs changing?', placeholder: notes.length ? 'Add a note or clarify earlier feedback. Previous notes are kept.' : 'Describe the revision you want (up to 4000 characters)' });
            if (!feedback?.trim()) continue;
          }
          const reviewer = await context.ui.dialog.prompt({ title: 'Reviewer label', placeholder: 'Your name or review label (not authenticated identity)' });
          if (!reviewer?.trim()) continue;
          const message = `Asset: ${opened.name}\nRevision: ${opened.revision_hash}\nReviewer: ${reviewer.trim()}\n\n${decision === 'approve'
            ? 'I reviewed this exact artwork, watched its motion if animated, and checked layout/collision data if a tileset. Record approval only; do not import.'
            : (notes.length ? 'Add this note while keeping all earlier feedback. This version will still need changes:\n' : 'Record these requested changes and block further import of this revision:\n') + feedback.trim()}`;
          if (!await context.ui.dialog.confirm({ title: decision === 'approve' ? assetStep(3, 'Approve exact revision?') : assetStep(2, 'Save requested changes?'), message, label: { confirm: decision === 'approve' ? 'Approve revision' : 'Request changes', cancel: 'Cancel' } })) continue;
          const result = await invoke({ action: decision, ticket, reviewer: reviewer.trim(), ...(feedback ? { feedback: feedback.trim() } : {}) });
          status = result.status;
          context.ui.toast.show({ title: 'Your assets', message: decision === 'approve' ? 'Step 3 complete. Next: Add or update in project, review the plan, then confirm (step 4).' : result.result?.action === 'keep_feedback' ? 'That note is already saved. Next: Make revised version, then review its result.' : 'Feedback saved. Next: Make revised version, then review the new candidate.', variant: 'success' });
        }
      } catch (error) {
        const message = explain(error);
        context.ui.toast.show({ title: 'Your assets', message, variant: 'error', duration: 10000 });
        await context.ui.dialog.alert({ title: 'Asset action stopped — details', message: message + '\n\nNo action was automatically retried. Confirmed decisions and saved feedback remain recorded. Keep this message if you need help; do not delete existing work to bypass a refusal.' });
      } finally {
        if (ticket) { try { await invoke({ action: 'cancel', ticket }); } catch { /* Expired/unloaded ticket: no decision is retried. */ } }
        busy = false;
      }
    },
  };
}
