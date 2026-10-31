// Use TextRenderable's public StyledText setter directly. This avoids losing
// per-run RGB styles while a reactive nested JSX span tree is reconciled.
export function paintCanvas(node, canvas, StyledText, RGBA) {
  node.content = new StyledText(canvas.map((span) => ({
    __isChunk: true,
    text: span.text,
    fg: RGBA.fromHex(span.color),
    attributes: 0,
  })));
}
