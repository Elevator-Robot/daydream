# Previous-version preview comparison — 2026-11-08

## Requested improvement

The user requested older versions in the asset preview so they can judge revisions
beside the earlier artwork and saved feedback without remembering asset names.

## Implemented experience

- **Compare with previous version** opens the earlier reference beside the fixed
  candidate under review, with an **Older version** picker and saved notes beneath
  each panel. New drafts are labelled **New candidate**; historical or approved
  selections are labelled **Selected version**.
- **Artwork scale** uses one native-pixel multiplier for both panels, including
  normalization of enlarged animation motion PNGs. Large images scroll instead of
  being independently resized; narrow screens stack the panels.
- **Replay motion** restarts both visible versions, including non-looping clips.
  Changing the comparison reference also restarts playback. Clip timing is retained;
  this is not a frame-synchronized animation editor.
- The original review ticket and selected hash remain fixed. Historical references
  cannot approve, import, or silently replace that selection.
- Discovery uses the shared asset catalog and recorded parent hashes, with bounded
  same-kind/same-ID history. Every embedded reference is validated. Missing, corrupt,
  oversized or denied history produces explicit notices rather than hiding the
  selected artwork or substituting a different parent without explanation.

## Automated checks

```sh
DAYDREAM_TEST_PYTHON=/tmp/opencode/daydream-sprites-test-venv/bin/python \
  node --test tests/preview.test.mjs
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The targeted preview suite passed 17 tests with the optional graphical game-launch
case skipped. Added checks cover ancestry before timestamps, unrelated/newer
revision exclusion, hash deduplication, bounded history, escaped notes/names and
the exact script CSP hash. Real backend fixtures cover three versions of every
asset kind, retained feedback, reference corruption, current-candidate corruption,
denied history discovery, cancellation and normalized animation scale.

The review suite additionally verifies that approving the displayed new candidate
writes only its exact approval; a historical reference with requested changes
stays blocked. The dependency-free full run passed **169 tests with 70 optional
skips**. The first optional full run exceeded the review suite's old 60-second
subprocess limit after the added real history inspections. Its bounded timeout was
increased to 120 seconds. The final full optional run passed **all 169 tests** in
181.6 seconds, including the Node suites and isolated real-Godot checks.
`git diff --check` passed, and **153 local documentation links** resolved.

## Actual browser rendering and interaction

A synthetic project under `/tmp/opencode/daydream-compare-ui-*` contains three
small floor revisions and a two-frame non-looping animation with a revised
palette. The real preview service generated the standalone HTML. An isolated
Chromium profile rendered it with the actual CSP in force.

Browser checks verified:

- Expanding comparison reveals the previous version; changing the picker changes
  only the reference panel. The selected revision hash remains fixed.
- Both floor layouts measure 256 CSS pixels wide at 4×, then 128 pixels at 2×.
- At a 600-pixel viewport the panels stack and do not overflow the page horizontally.
- No JavaScript exceptions or HTTP(S) document requests occur.
- Visible animation previews load their local PNG blobs successfully. Captured
  frame pixels changed from `(102, 153, 221)` at the start to `(255, 204, 136)` at
  the end, then returned to `(102, 153, 221)` after **Replay motion**.

Desktop and narrow-layout screenshots were opened and visually inspected. The
previous/new labels, equally sized floor images, darker revised edges and saved
feedback were visible and readable. Captures and driver scripts are temporary
machine-local evidence, not shipped game assets or a human artwork approval.

No actual user configuration, game project, previous revision, dependency or
external service was changed for validation. This verifies the preview experience,
not new game integration, graphical Godot gameplay or user branch acceptance.
