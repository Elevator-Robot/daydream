# Native Godot sprite previews — 2026-11-09

## Request

After existing sprites became visible in Sprites, the user reported that the
dashboard still displayed whole sprite sheets. Existing sprites should use the
same individual-frame and animation-gallery presentation as generated artwork.

## Implementation

- A bounded data-only Godot reader extracts SpriteFrames arrays, texture references,
  AtlasTexture regions, clip names, weighted frame durations, FPS and saved loops.
- Static Sprite2D regions and hframes/vframes grids provide explicit crop data too.
- Catalog results carry scanned dependency paths into inspect/media calls. The
  Python operation plan declares those reads before any resource is parsed. No
  unscanned references, project scripts or Godot process are executed.
- Source-image plus resource-byte hashes invalidate media after metadata edits.
- Thumbnails and overview show individual pixels cropped from the source sheet.
  Native clips share the existing PNG/APNG gallery, replay and frame explorer.
  Review-only repetition does not change recorded gameplay loops.
- Project file identity remains distinct from generated/approved revisions. Native
  clip cards do not offer managed-candidate review commands or invent pivots.
- Unsupported layouts are not guessed. Generic/folder-only images without frame
  definitions retain an explicitly explained original-image fallback. Margins,
  nested cropped atlases, multi-sheet/mixed-size clips and ping-pong playback are
  not approximated. Resource, parser, pixel, decoded-memory and output limits apply.

## Evidence

Read-only shared-operation inspection of Wonderer returned **96 × 96** frames
instead of its **576 × 384** sheet, with the original player-scene dependency and
five recorded clips (`Idol` and four walk directions), using 24 distinct source
frames. All five motion previews decoded successfully and original file hashes
remained unchanged. No game files were changed or artwork adopted/imported.

An isolated Chromium fixture used only bundled slime artwork arranged as a two-frame
sheet. It verified cropped 32px card/overview images, the shared native clip card,
saved one-shot status, source-frame tab, generic-image separation and unchanged
image/resource hashes. Chromium's ImageDecoder confirmed both APNG frames. No
JavaScript exceptions occurred in the successful run. The screenshot was opened
and inspected; it shows the normal gallery card, checkerboard preview, metadata,
Replay and Frames & timing controls, not a full sheet. This does not constitute
human approval of the user's artwork or gameplay acceptance.

## Checks

```sh
# dashboard/
npm run check
npm run build

# repository root
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
node /tmp/opencode/daydream-native-gallery-t0e83aqx/check.mjs
git diff --check
```

All **191 tests passed** with optional tools, including isolated Godot fixtures.
The dependency-free suite passed with **89 optional skips**. Type checking,
production build and browser checks passed. Regressions cover crop pixel identity,
frame duration weighting, native names containing spaces, saved one-shot APNG,
metadata invalidation, explicit read grants, invalid regions, memory budgets and
Sprite2D grids. Source files and prior documentation work were preserved.
