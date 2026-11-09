import { Rpc } from '@opencode/plugin/rpc';

export const Dashboard = Rpc.define({
  id: 'daydream.dashboard',
  methods: { call: {
    input: { type: 'object', properties: {
      sessionID: { type: 'string', minLength: 1, maxLength: 100 },
      project: { type: 'string', minLength: 1, maxLength: 4096 },
      action: { enum: ['catalog', 'inspect', 'media'] },
      path: { type: 'string', minLength: 1, maxLength: 4096 },
      kind: { enum: ['sprite', 'animation', 'tileset', 'image'] },
      image: { type: 'string', maxLength: 64 },
      resources: { type: 'array', maxItems: 500, items: { type: 'string', minLength: 1, maxLength: 4096 } },
      revision_hash: { type: 'string', minLength: 64, maxLength: 64 },
    }, required: ['sessionID', 'project', 'action'], additionalProperties: false },
    output: { type: 'object', properties: {}, additionalProperties: true },
    errors: { dashboard_failed: { type: 'object', properties: {}, additionalProperties: false } },
  } }, events: {},
});
