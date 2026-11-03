import { Rpc } from "@opencode/plugin/rpc";
import { previewInput } from "./preview-contract.js";

export const Preview = Rpc.define({
  id: "daydream.preview",
  methods: { call: {
    input: previewInput, output: { type: "object", properties: {}, additionalProperties: true },
    errors: { preview_failed: { type: "object", properties: {}, additionalProperties: false } },
  } },
  events: {},
});
