// Foreground-only retro-cyberpunk styling. Never paint a background or change
// the terminal's font/theme. The real ttfx engine still owns all motion.
export const PALETTE = {
  laser: ["ffffff", "00f5ff", "ff2bd6"],
  cooling: ["fff2cc", "ffd166", "ff2bd6"],
  sparks: ["ffffff", "ffd166", "ff2bd6", "662266"],
  final: ["ff2bd6", "9d4dff", "00f5ff"],
};

export function effectThemeArgs() {
  return [
    "--laser-gradient-stops", ...PALETTE.laser,
    "--cool-gradient-stops", ...PALETTE.cooling,
    "--spark-gradient-stops", ...PALETTE.sparks,
    "--final-gradient-stops", ...PALETTE.final,
    "--final-gradient-direction", "horizontal",
  ];
}

export function staticArtwork(text) {
  const lines = text.split("\n");
  const width = Math.max(1, ...lines.map((line) => [...line].length));
  const stops = PALETTE.final.map((hex) => hex.match(/../g).map((channel) => parseInt(channel, 16)));
  return lines.map((line) => [...line].map((character, column) => {
    const position = column / Math.max(1, width - 1) * (stops.length - 1);
    const index = Math.min(stops.length - 2, Math.floor(position));
    const blend = position - index;
    const rgb = stops[index].map((channel, i) => Math.round(channel + (stops[index + 1][i] - channel) * blend));
    return `\x1b[38;2;${rgb.join(";")}m${character}`;
  }).join("") + "\x1b[0m").join("\n");
}
