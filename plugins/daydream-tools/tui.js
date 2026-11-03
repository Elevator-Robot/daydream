import { Plugin } from '@opencode/plugin/tui';
import { createBrowser } from './browser.js';
import { previewCommand } from './preview-command.js';

export default Plugin.define({
  id: 'daydream.preview.tui',
  setup(context) {
    if (context.options.enabled === false) return;
    const browser = createBrowser();
    const controller = new AbortController();
    const command = previewCommand(context, async input => {
      const session = context.data.session.get(input.sessionID);
      const location = session?.location ?? context.location ?? context.data.location.default();
      const result = await context.client.rpc.call({ rpcID: 'daydream.preview', method: 'call', input, location: { directory: location.directory } }, { signal: controller.signal });
      return result.output;
    }, browser);
    context.keymap.layer(() => ({ mode: 'global', commands: [command] }));
    return async () => { controller.abort(); await browser.dispose(); };
  },
});
