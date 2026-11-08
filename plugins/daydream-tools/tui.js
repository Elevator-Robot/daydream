import { Plugin } from '@opencode/plugin/tui';
import { createBrowser } from './browser.js';
import { previewCommand } from './preview-command.js';
import { assetsCommand } from './assets-command.js';
import { createDashboardManager } from './dashboard-bridge.js';

export default Plugin.define({
  id: 'daydream.preview.tui',
  setup(context) {
    if (context.options.enabled === false) return;
    const browser = createBrowser();
    const controller = new AbortController();
    const call = rpcID => async (input, options = {}) => {
      const session = context.data.session.get(input.sessionID);
      const location = session?.location ?? context.location ?? context.data.location.default();
      const signal = options.signal ? AbortSignal.any([controller.signal, options.signal]) : controller.signal;
      const result = await context.client.rpc.call({ rpcID, method: 'call', input, location: { directory: location.directory } }, { signal });
      return result.output;
    };
    const preview = call('daydream.preview');
    const dashboards = createDashboardManager(call('daydream.dashboard'), url => browser.openURL(url));
    browser.openDashboard = async sessionID => {
      const session = context.data.session.get(sessionID);
      if (!session?.location?.directory) throw new Error('Reopen the project session before opening its dashboard');
      return dashboards.open(sessionID, session.location.directory);
    };
    const assets = assetsCommand(context, call('daydream.review'), preview, browser);
    const command = previewCommand(context, preview, browser);
    context.keymap.layer(() => ({ mode: 'global', commands: [command, assets] }));
    return async () => { controller.abort(); await dashboards.dispose(); await browser.dispose(); };
  },
});
