# Richer tile collisions — 2026-11-05

## Scope and implementation

The user explicitly chose richer collisions rather than editor-visible layouts.
Work extends existing tileset create/edit/inspect, review and export capabilities
with bounded convex pieces, half-pixel coordinates, ramp presets, and one-way
platforms/margins. No actual game, user configuration, engine pin or controller was
modified. No package/provider/service was added. The baseline was `ce9da22`.

Existing solid-rectangle sources remain untouched. New explicit-geometry sources
have a hash-bound collision overlay plus exact coordinate/settings listings.
Native and CLI schema validation share the same geometry library; new collision
revisions still need approval, and approval/import are not automatic.

## Engine evidence

Godot **4.7.2.stable.arch_linux.ed1daf0bf**, Pillow **12.3.0**, Linux. An isolated
synthetic TileMapLayer fixture exercised:

- Correct per-tile polygon counts, multiple pieces and centered coordinate export.
- A half-pixel vertex preserved as `Vector2(-8, -7.5)` in Godot's resource.
- Both slope directions: downward ray hit positions and expected diagonal normals.
- A passable middle gap between two convex pieces, an empty collision tile and
  the existing legacy full rectangle.
- A one-way flag and .75-pixel margin read back from the imported TileData.
- A real `CharacterBody2D` moving upward through the platform, then landing on
  its top from above; rays alone were not treated as proof of one-way behavior.

The focused command is:

```sh
GODOT_BIN=/usr/bin/godot /tmp/opencode/daydream-sprites-test-venv/bin/python \
  -m unittest discover -s tests -p test_collisions.py -v
```

The full development suite also covers mathematical validation, invalid/contradictory
input, native grants, immutable edits/fresh approval, overlay tampering, browser
rendering and existing sprite/animation/terrain/review regressions. Commands and
optional dependency boundaries are documented in DEVELOPMENT.md.

Full validation completed successfully:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Results: **145 tests passed** in the optional Pillow/Godot/ttfx environment; the
dependency-free run passed with **54 optional tests skipped**. Live native
`daydream_describe` also returned the new `tileset.edit` polygon and preset schemas.

## Compatibility and visual evidence

A previously generated/approved synthetic garden-wall bundle loaded without
modification and still reported `approved`. Its unchanged revision hash was
`cdebd094678310dfc0d219d054f7ac88b12d3fc445238229b0cc38a4fab5cdd2`.
Tests separately check legacy source/artifact preservation and new unapproved
collision edits. This does not authorize changing any existing user assets.

A new synthetic geometry fixture was imported, rendered with the normal graphical
Godot renderer and its viewport image captured through Godot's own API. The actual
capture, numbered preview and collision coverage PNG were read and inspected.
The rendered ramps, two-piece gap, thin platform band and full rectangle were
visible and aligned with their flat demonstration tiles. Preview colors showed
yellow solid and cyan one-way coverage. Exact coordinates remain available because
raster previews approximate half-pixel geometry.

Captures/bundles live in temporary `/tmp/opencode/daydream-collision-visual-*`
directories and may disappear; this report retains the observations, not durable
image files. The fixture uses flat demonstration artwork and synthetic approvals.
No human has approved art or play feel in a real game from these checks. Slopes,
one-way margins and controller settings still need game-specific playtesting.
