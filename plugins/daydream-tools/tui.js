import { Plugin } from '@opencode/plugin/tui';
import { createBrowser } from './browser.js';
import { previewCommand } from './preview-command.js';
import { assetsCommand } from './assets-command.js';

export default Plugin.define({
  id: 'daydream.preview.tui',
  setup(context) {
    if (context.options.enabled === false) return;
    const browser = createBrowser();
    const controller = new AbortController();
    const call = rpcID => async input => {
      const session = context.data.session.get(input.sessionID);
      const location = session?.location ?? context.location ?? context.data.location.default();
      const result = await context.client.rpc.call({ rpcID, method: 'call', input, location: { directory: location.directory } }, { signal: controller.signal });
      return result.output;
    };
    const preview = call('daydream.preview');
    const assets = assetsCommand(context, call('daydream.review'), preview, browser);
    const command = previewCommand(context, preview, browser);
    context.keymap.layer(() => ({ mode: 'global', commands: [command, assets] }));
    return async () => { controller.abort(); await browser.dispose(); };
  },
});
