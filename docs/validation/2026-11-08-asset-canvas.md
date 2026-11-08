# Artwork-first detail canvas — 2026-11-08

The user requested better space utilization and a zoomable space for the actual
sprite/image while inspecting an asset. The asset overview now places a large
viewport beside a compact information/palette/feedback rail, with a shorter header
and controls. Narrow layouts place metadata below the canvas.

## Interaction

- Wheel/pinch zoom anchors the source coordinate beneath the pointer/gesture.
- Mouse/touch drag pans, with capture and release/cancellation cleanup.
- Fit, native 1:1, zoom slider/buttons, Reset view and double-click are supported.
- Checkerboard/dark/light backgrounds and a 4×+ source-pixel grid aid inspection.
- Focused keyboard zoom/pan/Fit controls are available without stealing Escape.
- Comparison uses a shared fixed scale; its two images can be independently panned.
- Animation remains a native APNG image, retaining the preview-only replay behavior.

The new React component and its pure coordinate helpers do not read project files
themselves; they receive validated media from the existing dashboard operations.
No asset source, approval, import or gameplay changes are part of this work.

## Checks

```sh
# dashboard/
npm run check
npm run build

# repository root
node --test tests/dashboard.test.mjs
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Pure-math checks verify integer Fit enlargement, bounded fractional scales, pointed-
pixel invariance and reversal after panning/zooming. The actual Chromium fixture
checks wheel anchoring, 70-pixel drag, 1:1, keyboard zoom/pan, Fit/reset, pixel-grid
visibility, background selection and touch pinch. Source-frame/animation access,
full-width details, return focus, existing atlas discovery and the 162-tile explorer
are rechecked. Desktop and 600-pixel overview screenshots are opened and inspected.

The first browser check exposed lost pointer capture while the button remained
pressed; pointer handling now recaptures during movement and cleans up on global
release. The following browser run verified the expected pan translation.

The final browser interaction run passed with no JavaScript exceptions. Screenshots
show a substantially larger centered sprite, compact controls and side-by-side
metadata at desktop width; at 600 pixels the canvas stays readable with metadata
below it and no horizontal page overflow. No user project or configuration was
changed. The full optional suite passed **all 178 tests**, including Node and
isolated Godot fixtures. The dependency-free run passed with **78 optional skips**.
Type checking, production bundling, the actual TUI/RPC check and `git diff --check`
passed. **176 local documentation links** resolved. Temporary
screenshots/driver scripts remain under `/tmp/opencode/daydream-dashboard-visual-*`;
they are validation evidence, not game assets or human artwork approval.
