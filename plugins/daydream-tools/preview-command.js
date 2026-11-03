export function previewCommand(context, call, browser) {
  let busy = false;
  return {
    id: 'daydream.preview', title: 'Preview game or asset', group: 'Daydream', palette: true,
    slash: { name: 'preview', arguments: true },
    enabled: () => context.ui.router.current().type === 'session',
    async run(argument = '') {
      if (busy) return;
      const route = context.ui.router.current();
      if (route.type !== 'session') return;
      const sessionID = route.sessionID;
      busy = true;
      try {
        const text = String(argument).trim();
        let action = text.split(/\s+/, 1)[0];
        const remainder = text.slice(action.length).trim();
        if (!action) action = await context.ui.dialog.select({ title: 'Daydream preview', options: [
          { title: 'Game', description: 'Run the configured main scene in graphical Godot', value: 'game' },
          { title: 'Asset', description: 'Review a sprite, animation or environment tileset in your browser', value: 'asset' },
          { title: 'Status', description: 'Inspect the tracked game process and launch diagnostics', value: 'status' },
          { title: 'Stop game', description: 'Stop only the game Daydream launched', value: 'stop' },
        ] });
        if (!action) return;
        if (!['game', 'asset', 'status', 'stop'].includes(action) || (action !== 'asset' && remainder)) throw new Error('Use /preview game, asset [revision path], status, or stop');
        const invoke = async (request) => {
          const result = await call({ sessionID, ...request });
          if (!result?.ok) throw new Error(result?.error?.message ?? 'Preview failed; use /preview status for game diagnostics');
          return result;
        };
        if (action === 'game') {
          const accepted = await context.ui.dialog.confirm({ title: 'Run game preview?', message: 'Godot will execute this project’s code and may write .godot/, imports and save data. It runs on the OpenCode server’s desktop. Use only a trusted project.', label: { confirm: 'Run game', cancel: 'Cancel' } });
          if (!accepted) return;
          const result = await invoke({ action });
          context.ui.toast.show({ title: 'Daydream preview', message: result.already_running ? 'Game preview is already running' : `Game preview: ${result.state}. Use /preview status for diagnostics.`, variant: result.state === 'running' ? 'success' : 'warning' });
        } else if (action === 'stop') {
          await invoke({ action });
          context.ui.toast.show({ title: 'Daydream preview', message: 'Tracked preview stopped; other Godot instances were not touched', variant: 'success' });
        } else if (action === 'status') {
          const result = await invoke({ action });
          await context.ui.dialog.alert({ title: 'Game preview status', message: `${result.state}${result.version ? '\nGodot ' + result.version : ''}${result.code !== undefined ? '\nExit: ' + result.code : ''}\n${result.diagnostics ?? ''}\n\nA running process is not proof of visual correctness or playtesting.` });
        } else {
          let bundle = remainder;
          if (!bundle) {
            const result = await invoke({ action: 'assets' });
            bundle = await context.ui.dialog.select({ title: 'Preview asset revision', options: [
              ...result.assets.map(asset => ({ title: asset.bundle, description: asset.kind, value: asset.bundle })),
              { title: 'Enter revision path…', description: 'For candidates outside the configured source directory', value: '\0manual' },
            ] });
            if (bundle === '\0manual') bundle = await context.ui.dialog.prompt({ title: 'Revision bundle path', placeholder: 'art/sprites/slime-v1' });
          }
          if (!bundle) return;
          if (!await context.ui.dialog.confirm({ title: 'Open asset preview?', message: 'Open a read-only sprite, animation or tileset viewer in your default browser. This does not approve or import the revision.', label: { confirm: 'Open preview', cancel: 'Cancel' } })) return;
          const result = await invoke({ action: 'asset', bundle });
          await browser.open(result.html);
          context.ui.toast.show({ title: 'Asset preview', message: 'Browser launch requested. Review the exact revision shown; nothing was approved.', variant: 'success' });
        }
      } catch (error) {
        context.ui.toast.show({ title: 'Daydream preview', message: String(error.message ?? error), variant: 'error', duration: 8000 });
      } finally { busy = false; }
    },
  };
}
