// One action definition shared by the slash-command RPC and model-facing tool.
export const previewInput = {
  type: "object",
  properties: {
    sessionID: { type: "string", minLength: 1, maxLength: 100 },
    action: { type: "string", enum: ["game", "status", "stop", "assets", "asset"] },
    bundle: { type: "string", minLength: 1, maxLength: 4096 },
  },
  required: ["sessionID", "action"], additionalProperties: false,
};
