# Asset review validation — 2026-11-05

## Scope

Verify the new integrated user review flow, not repeat the user's completed P0/P1
trials or claim a new real-game/art acceptance. The only initial working-tree edit
was the roadmap update; it was preserved and extended, not reverted.

## Automated evidence

Environment: OpenCode **2.0.32**, Godot **4.7.2.stable.arch_linux.ed1daf0bf**,
Pillow **12.3.0**, Linux. No engine or package was installed/upgraded for this work.

Commands completed successfully:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Results: **138 tests passed** with the optional environment/real Godot checks;
the dependency-free run passed with **50 optional tests skipped**. Node suites are
invoked by the Python-discovered adapter tests, not additional Python test counts.

- Shared Python review/approval/feedback/import core tested for sprites, animations
  and tilesets, with immutable revision-bound records and native decision refusal.
- Node tests drive the actual Python backend through the user-review service and
  check ticket/session/expiry, permission denial, cancellation, feedback and plan
  invalidation. Separate UI tests ensure approval never automatically imports.
- Existing Godot resource, terrain-painting, playback and physics tests remain part
  of the full optional-dependency suite. See DEVELOPMENT.md for test commands.

## Actual OpenCode TUI evidence

An isolated `opencode --standalone` instance ran under a pseudo-terminal (140×45).
Temporary XDG config/data/state/cache directories and installer destinations were
used under `/tmp/opencode/daydream-review-ui-*`; no actual user configuration or
existing game was modified. `tests/review_fixture.py` supplied three synthetic
bundles. A temporary TUI test driver created an empty Daydream session without a
model prompt, navigated to it, and invoked the actual `daydream.review` command.

Keyboard-driven native dialogs demonstrated:

1. Confirm browser opening for `art/dot`, explicitly select approval, enter the
   reviewer label `synthetic-review-fixture`, confirm the full revision, and accept
   the actual server permission request. The expected `approval.json` was written.
2. Separately choose import planning, select defaults, read/close the plan dialog,
   and explicitly confirm apply. The expected `assets/sprites/dot.png` appeared.
3. Open the synthetic animation, request changes, enter a note/reviewer, and confirm.
   `changes-requested.json` retained `Please revise this synthetic animation`, kind
   `sprite_animation`, its exact hash and a UTC timestamp.
4. Open the synthetic tileset and cancel. No tileset approval was written.

The original live run used the initial slash spelling `/review`; checking the
actual built-in command registry showed that OpenCode reserves that spelling for
code review. The product command was therefore namespaced to `/asset-review`
(`/preview review` and `/daydream-review` also lead to the same flow). The internal
command ID remains `daydream.review`.

**Final namespaced-command run:** completed again in a fresh isolated project,
typing `/asset-review` through the actual composer (not merely dispatching the
internal command ID). Approval, separate import, animation feedback and tileset
cancellation all produced the expected on-disk outcomes. The final synthetic
sprite approval timestamp was `2026-11-05T23:46:28.541684+00:00`; its hash was
`ade8262bf1fca5327f8410ff31fd92b5a2bc60465c305c42d99dc7e7e29a5001`.
The animation feedback timestamp was `2026-11-05T23:46:46.326142+00:00`.

## Defect found and fixed

The first live attempt stopped safely before approval because `xdg-open` stayed
alive longer than five seconds. The old browser helper incorrectly treated that
as failure and attempted to terminate the opener. It now catches immediate opener
failures but accepts a long-lived browser process without waiting for viewer exit
or killing it. A regression test covers the long-lived-opener case. The subsequent
live run completed approval/import/changes/cancel as described above.

## Limits

The terminal transcript and generated files are temporary machine-local artifacts,
not permanent screenshot evidence. Fixture approvals are synthetic test actions,
not a human art-quality verdict. No model request, paid provider, account connection,
new software, engine migration or user-game import was performed.
