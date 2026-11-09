# Latest candidate labels — 2026-11-08

## User-reported ambiguity

The current-candidate picker showed two same-named assets as raw `sprite_animation`
and `sprite` types, each with older revisions, without clearly identifying which
version was newest. The rows were separate asset kinds, each already representing
its latest saved candidate.

## Change

The shared catalog now exposes `is_latest` for each row, including history views,
using its existing per-kind/per-ID saved-file ordering. The picker shows **Latest**
or **Older** before friendly **Animation**, **Static sprite** and **Tileset** labels,
with UTC saved times and review state. Normal rows omit raw revision paths; those
remain in preview details. A larger native dialog and compact older count keep the
information readable. Listing order remains newest saved first, independently of
whether a candidate is approved or imported.

## Validation

Existing tests were reused for the reversible presentation change. Required checks:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The full optional run passed **all 169 tests**, including Node and isolated Godot
checks. The dependency-free run passed with **70 optional tests skipped**.
`git diff --check` passed, and **157 local documentation links** resolved.

An actual standalone OpenCode TUI used an isolated synthetic project under
`/tmp/opencode/daydream-latest-ui-*`, with three sprite and three animation
revisions sharing the friendly name “Whisp.” Synthetic manifest times were spaced
one minute apart for readable, deterministic ordering. The shared catalog reported
exactly one latest candidate for each kind. The registered `/assets` command was
dispatched by the fixture driver; history selection and closing used keyboard input.

The normal list displayed two **Latest** rows with distinct friendly types, saved
times, review state and older counts. **Show older revisions** displayed four
**Older** rows alongside the two latest ones. The initial narrow-dialog check
exposed truncated descriptions; the final large-dialog/compact-description check
passed. Project hashes were identical before and after browsing. No approval,
import, model request, user configuration or actual game asset was changed.

Temporary terminal transcripts are machine-local evidence, not artwork approval
or a new end-to-end game acceptance claim.
