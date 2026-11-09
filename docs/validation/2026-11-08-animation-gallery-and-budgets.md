# Unified clip gallery and animation resource budgets — 2026-11-08

## User direction

Nyx's animations were split into three source bundles and the dashboard defaulted
to the newest bundle, revealing only death. The user requested removal of the frame
limit, then replaced the pan/zoom picture design with an organized compact gallery
of looping previews.

## Implemented changes

- Removed the 32-source-frame, 64-step-per-clip and 128-total-step ceilings from the
  shared validator and native create/assemble/edit clip schemas. There is no
  replacement arbitrary frame-count maximum.
- Retained actual resource safeguards: 8 MiB editable source, 16-megapixel atlas and
  contact images with 16,384-pixel edges, 128 MiB decoded motion-frame data, and the
  existing encoded artifact/bundle bounds. Canvas, FPS and clip-duration validation
  remain. Native request/output byte budgets still apply independently.
- Check assembly/expanded recipes before allocating oversized source collections.
  Canonical CLI reads and revision loading now accept the same 8 MiB source budget.
- Contact sheets never fall through to zero/negative pixel scale; longer sheets
  may exceed the old 2048-pixel presentation height within image budgets. Existing
  small-bundle rendering and hashes are preserved.
- Replaced dashboard pan/zoom windows with compact PNG/APNG previews. The canvas
  component, gesture handlers and coordinate-only tests were removed rather than
  kept as an unused runtime feature. Pictures have no internal scrollbars.
- The sprite gallery displays every clip from all latest linked sets together.
  Older versions are optional, failures are shown per source, and each card retains
  timing, saved loop state, frame/contact data, feedback and source-set review identity.
  Replay only affects the browser; no gameplay-loop flags or approvals are changed.

## Validation

```sh
# dashboard/
npm run check
npm run build

# repository root
GODOT_BIN=/usr/bin/godot /tmp/opencode/daydream-sprites-test-venv/bin/python \
  -m unittest discover -s tests -p test_animations.py -v
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

All **182 tests** passed with optional Pillow/Godot/Node checks. The dependency-free
run passed with **80 optional skips**. Type checking and production build passed.

New regressions exercise 193 unique source frames / 257 ordered steps without schema
count caps; resource-budget refusals; long contact sheets with positive scale;
76-frame creation/assembly through shared operations and exact native grants;
rendering/APNG inspection/editing/import of 129 ordered steps; and actual Godot
loading of frame 75 at the expected atlas position. Earlier resource/playback tests
continue to pass.

## Nyx-specific isolated checks

Read-only inspection found 32 idle/attack frames, 16 hurt/vanish frames and 28 death
frames, for 76 in total. A canonical source containing all five clips was rendered
and loaded through the shared CLI/core in `/tmp/opencode/daydream-nyx-complete-*`.
The source was 853,249 bytes; all 76 frames and five names survived validation. This
was an isolated copy, not a new candidate written into the user's project.

Copied Nyx revisions were served in another disposable project through the real
dashboard bridge/backend. Chromium verified five fully loaded gallery previews:
idle, attack, hurt, vanish and death. No bundle selector, canvas surface or zoom
slider remained. Preview replay occurred, manual Replay and source frame inspection
worked, and the 600-pixel layout had no horizontal page overflow. No JavaScript
exceptions occurred. Actual screenshots were opened and visually inspected.

PNG/APNG is retained rather than introducing GIF palette loss or replacing source
art. Existing user bundles, feedback, approvals, imports and game scenes were not
rewritten or consolidated automatically. Temporary driver/capture paths are local
verification evidence, not user artwork approval or gameplay acceptance.
