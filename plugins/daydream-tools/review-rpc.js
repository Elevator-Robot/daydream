import { Rpc } from '@opencode/plugin/rpc';

export const Review = Rpc.define({
  id: 'daydream.review',
  methods: { call: {
    input: { type: 'object', properties: {
      sessionID: { type: 'string', minLength: 1, maxLength: 100 },
      action: { type: 'string', enum: ['open', 'approve', 'changes', 'plan', 'import', 'cancel'] },
      bundle: { type: 'string', minLength: 1, maxLength: 4096 },
      ticket: { type: 'string', minLength: 1, maxLength: 100 },
      reviewer: { type: 'string', minLength: 1, maxLength: 120 },
      feedback: { type: 'string', minLength: 1, maxLength: 4000 },
      name: { type: 'string', minLength: 1, maxLength: 48 },
      destination: { type: 'string', minLength: 1, maxLength: 4096 },
      layout: { type: 'string', enum: ['runtime', 'editor'] },
      godot: { type: 'string', minLength: 1, maxLength: 4096 },
      godot_version: { type: 'string', minLength: 5, maxLength: 128 },
    }, required: ['sessionID', 'action'], additionalProperties: false },
    output: { type: 'object', properties: {}, additionalProperties: true },
    errors: { review_failed: { type: 'object', properties: {}, additionalProperties: false } },
  } },
  events: {},
});
