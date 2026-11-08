# Compact, non-trapping artwork canvases — 2026-11-08

The user reported overlapping static/animated previews, excessive canvas space and
ordinary scrolling unexpectedly shrinking the artwork.

## Fixes

- Removed sticky positioning from the artwork grid child. Previously it could
  remain stuck while the following animation section moved beneath it.
- Main canvas heights are bounded to 240–360 pixels, animation viewports to 280
  pixels, with compact controls. Fit enlargement is capped at 8× instead of 16×.
- Unmodified wheel events are not intercepted: they scroll the page. Deliberate
  Ctrl/Cmd+wheel, touch pinch, keyboard and explicit controls still zoom.
- Drag completion explicitly releases pointer capture. Mouse moves with no pressed
  primary button clear stale drag state; window blur clears captured pointers too.
  No pointer-lock or cursor-confinement API is used.

## Checks

```sh
# dashboard/
npm run check
npm run build

# repository root
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The actual synthetic Chromium dashboard fixture checks that ordinary wheel input
increases the inspector scroll position without changing image scale, Ctrl+wheel
still anchors zoom, and releasing a drag leaves no pointer capture or panning
class. It verifies non-overlapping artwork/animation rectangles after scrolling,
the new height bounds, Fit/1:1, keyboard controls, backgrounds, grid and pinch.
Existing collection return, source frames, tileset classification and the 162-tile
explorer still pass. No JavaScript exceptions occurred.

Actual screenshots were opened and inspected: the static canvas is shorter and
the animation section starts below it without overlap; scrolling to animations
does not bring the static image over the animation viewport. No actual user project
or configuration was changed. The full optional suite passed **all 178 tests**,
including Node and isolated Godot checks. The dependency-free run passed with
**78 optional skips**. Type checking, production build and `git diff --check` passed.
