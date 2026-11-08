# Preview-only animation looping — 2026-11-08

## User selection

The user wanted recurring animation playback. Inspection showed that the selected
animation's idle clip already looped while its attack was one-shot. The user
explicitly chose **Preview only**, preserving saved/gameplay loop settings.

## Implementation

- Animation viewers now default **Loop preview** to on. Visible, multi-frame
  one-shot clips automatically restart after each complete cycle. Existing looping
  clips use their native playback rather than restarting with another clip's timer.
- Each clip displays its saved playback mode. Turning the checkbox off replays
  using the saved settings; **Replay motion** remains available manually.
- The shared inspector returns the saved loop flag and total rounded APNG duration.
  The browser caches each embedded PNG blob and replaces/revokes only its local URL
  on replay. Source files, manifests, motion images and Godot resources are untouched.
- Comparison changes, hidden pages and page exit clear replay timers. Visible
  playback resumes on return, including a restored browser-history page.

## Checks

```sh
DAYDREAM_TEST_PYTHON=/tmp/opencode/daydream-sprites-test-venv/bin/python \
  node --test --test-name-pattern='preview looping|preview-only looping' tests/preview.test.mjs
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The two targeted tests passed. The full optional run passed **all 169 tests**,
including Node and isolated Godot checks; the dependency-free run passed with
**70 optional tests skipped**. Deterministic scheduler checks cover repeated
one-shots, independent native loops, static images, toggle/manual replay,
comparison selection and hidden/page lifecycle cleanup. A real-backend fixture
checks the 666 ms rounded duration of a two-frame 3 FPS clip and byte-for-byte
source/manifest/motion preservation.

## Actual selected-asset preview

A read-only call through the real `daydream.preview` RPC produced the selected
Whisp animation's HTML, including the new control. Isolated Chromium rendered
that snapshot under `/tmp/opencode/daydream-loop-preview-*` with its actual CSP.

The browser observed three automatic attack replays while the idle image was not
restarted, then two replays of the compared older attack. Hidden-reference replay
stopped after switching versions. Disabling the checkbox stopped automatic image
restarts; manual replay worked, and enabling it resumed looping. Captured attack
frames visibly differed; the full screenshot was opened and inspected, showing
the loop control and saved playback labels alongside the selected/older artwork.

All nine files in the selected source bundle retained their hashes. The selected
revision hash remained fixed, and there were no JavaScript exceptions or HTTP(S)
document requests. No new revision, approval or import was created. The temporary
captures are machine-local verification, not user artwork approval or a gameplay
playtest. Browser replay scheduling is not a guarantee of frame-perfect Godot timing.
