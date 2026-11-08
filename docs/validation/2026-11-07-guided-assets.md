# Guided asset lifecycle — 2026-11-07

Branch: `feat/editor-visible-tile-layouts`; baseline `6c2e0c4`. The user explicitly
requested friendly naming, automatic history, safe create/update and quality-of-life
guidance. No new branch publication/merge was requested, and no Potion Shop files
were used as mutation fixtures.

## Implementation

- Existing renderer operations accept friendly labels and optional output locations;
  canonical source IDs remain validated and human labels are retained in provenance.
- A shared Python lifecycle module discovers hidden/legacy candidates and current
  managed-output status, supplies guided choices and validates stable update identity.
- The existing import store now supports explicit, exact-plan managed updates with
  full old-byte/index/record snapshots before any replacement. It preserves unrelated
  records/annotations and leaves Godot sidecars untouched. Legacy/new imports still
  refuse overwrites; copy mode automatically selects unused filenames.
- `/assets` and the review/preview pickers show friendly current/history choices,
  status, help and a bounded thumbnail gallery. Add/update summaries lead the flow;
  paths and hashes remain inspectable under Details. Real failures stay visible.
- Post-import guidance can open the exact scene in a permissioned game preview
  without changing the main scene; editor opening itself remains explicit user action.

## Checks

The Python suite includes friendly-name conversion, hidden deterministic revision
planning, current/history discovery, copies with filename/registry collisions,
all-kind updates, exact recovery bytes, preserved sidecars, manual edits, tile-ID
compatibility, native read/write grants and simulated interruption during replacement.
Node tests cover the actual Python-backed user-review service's update flow,
friendly UI names, optional Details, history selection, thumbnail documents, and
scene-specific preview argv. Existing Godot fixtures remain in the full suite.

Commands:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Latest full run: **166 Python-discovered tests passed**; dependency-free run passed
with **67 optional tests skipped**. Node cases are invoked through Python adapters.
No dependencies or engine were installed/upgraded.
Live native `daydream_assets_list` discovery and a read-only call in the Daydream
repository also succeeded; it reported no game assets and wrote nothing.

## Actual TUI check

An installed whole-directory-link plugin ran in standalone OpenCode **2.0.32** under
a pseudo-terminal with temporary XDG config/data/cache/state and a synthetic Godot
project under `/tmp/opencode/daydream-guided-assets-*`. The test driver created an
empty session without model prompts and dispatched the registered `daydream.assets`
command; user-visible dialogs were driven with keyboard input.

Verified on disk after real dialogs:

- A hidden staged sprite called **Moonlight Floor** appeared in the asset picker.
- Explicit approval, **Add a separate copy**, the friendly rename **Moonlight Floor!**,
  plain-language plan and separate confirmation created `assets/sprites/moonlight-floor.png`.
- A subsequent revision was created with no output path and inherited its friendly
  label. In a fresh standalone session, explicit approval and **Update Moonlight Floor!**
  replaced that same resource path. The exact previous PNG bytes were retained in
  `.daydream/history/imports/moonlight-floor/<plan-hash>/files/...`.

The initial combined test driver failed to navigate reliably back into a second
review after finishing the first. It was split into fresh-session add/update runs;
both final user-visible flows completed. Bare slash/alias keyboard submission was
not the evidence for execution: the test dispatched the registered command ID.
At that time, `/assets` was a dedicated no-argument slash command. The subsequent
naming simplification makes it the sole asset-management command, optionally
accepting a revision folder. Its internal command ID is still `daydream.assets`.
The separate asset-review command and its aliases and preview-review route have
been removed. No change patches OpenCode's command menu.

## Boundaries

Synthetic approvals are not approval of user artwork. The live fixture verifies
the guided UI and resulting bytes; unit/backend tests cover all three asset types
and denial/interruption paths. Manual real-game acceptance is still the user's task.
No legacy asset folder was migrated/deleted, no history pruned, no existing user
configuration changed, and no actual game/editor was killed or rewritten.

Updates are checked per-file under managed locks, not an atomic multi-file filesystem
transaction. Unsaved editor buffers and hostile/uncooperative concurrent writers
are outside the guarantee. Interrupted updates retain recovery evidence and block
blind retry; there is no automatic destructive rollback or snapshot-restore command.
