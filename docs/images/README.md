# Documentation screenshots

Captured from the actual built dashboard on 2026-11-09, using an isolated Moonlight
Workshop sample project. The screenshots are not mockups or user-game captures.

| Image | View | Sources |
| --- | --- | --- |
| `project-collection.png` | Full project collection at 1280 × 1080 | Repository slime, floor and wall examples; sample palette variants and managed statuses |
| `animation-gallery.png` | Cropped animation-gallery region | Idle/blink from `examples/slime-idle.animation.json`; a bounce made by shifting the same sample sprite's rows through the shared recipe input |
| `tileset-explorer.png` | Full tileset detail view at 1280 × 900 | `examples/floor.sprite.json`, `examples/wall.sprite.json` and the shared 162-terrain transition operation |

Color variants retain the original sample pixel grid. Images, animation, tilesets
and synthetic review/import state were created with the existing shared operations
in a disposable project, not by changing a real game. No Nyx, Whisp or other user
game artwork is included.

The dashboard was served by its real bridge and shared backend, rendered in an
isolated Chromium profile, and captured with its normal CSS, controls and CSP.
The collection waited for all eight thumbnails to load; the gallery waited for
all three animated images; the tile view loaded its atlas and selected tile 10.
The gallery image is a direct crop of the live gallery element, not a composited
or relabelled scene. These static images illustrate controls, not proof of motion
review, gameplay quality or user artwork approval.

The temporary fixture/driver is under `/tmp/opencode/daydream-readme-*`. For future
updates, use the bundled examples and the current dashboard, avoid user-owned game
assets, and inspect every actual capture before replacing a screenshot. These
files do not grant a new license or select one for the repository.
