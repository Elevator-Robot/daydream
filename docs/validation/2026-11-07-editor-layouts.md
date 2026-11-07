# Editor-visible layout validation — 2026-11-07

## Scope

Branch: `feat/editor-visible-tile-layouts`, from `208a7f5`. The user selected
editor-visible layouts after the collision work. Existing game/configuration
files were not modified; P0/P1 remain user-confirmed and the newer collision
manual trial has not been reported complete.

Implementation adds `tileset.editor_import`, using the existing approved source,
resource builder and safe import store. Native/UI previews require separate
execution permission and run the detected, project-checked engine only against a generated
scratch project. Outputs contain no layout script; the old import remains available.

## Research and determinism

The prototype used documented `set_cell`, `PackedScene.pack`, `ResourceSaver.save`
and `ResourceLoader` interfaces. Initial repeated saves had different bytes because
Godot generated random external labels/node tracking IDs. Only those documented
labels in the fresh one-node output are stabilized; private tile payloads and the
engine-selected scene format are never authored/decoded in Python. A fresh Godot
process reloads the normalized output and verifies every cell and script absence.
Repeated previews then produced identical scene bytes and import-plan hashes.

Sources: [PackedScene](https://docs.godotengine.org/en/stable/classes/class_packedscene.html),
[ResourceSaver](https://docs.godotengine.org/en/stable/classes/class_resourcesaver.html),
[TSCN labels](https://docs.godotengine.org/en/stable/engine_details/file_formats/tscn.html).

## Automated evidence

Commands:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The initial full branch suite passed **151 tests** (Pillow **12.3.0**, Godot
**4.7.2.stable.arch_linux.ed1daf0bf**); the dependency-free run passed with **57
optional tests skipped**. Node test cases run through Python-discovered adapters.
No dependency/engine installation was performed. Live native describe also
confirmed discovery of `daydream_tileset_editor_import` with explicit
`engine_serialization:true` metadata.

The suite exercises:

- Execution-grant refusal before an engine call; separate native permission denial.
- Owned process-group timeout/output-limit cleanup.
- Deterministic preview/apply, explicit version mismatch, stale plans, and refusal
  to overwrite a manually modified scene/index.
- A deliberately invalid target autoload, detecting accidental execution of target
  game code. Only later explicit verification opens that disposable target.
- Cells present in `PackedScene.instantiate()` before tree entry/`_ready()`;
  one-way resources retained, script absence, manual erase/paint/save/reload, and
  no reset when the saved scene is subsequently added to a running tree.
- User-review mode/engine selection and the real Python-backed review service's
  separately permissioned editor-mode plan/apply.

## Actual graphical editor evidence

A disposable project under `/tmp/opencode/daydream-editor-visual-*` was populated
through the shared operations, with a synthetic approval label and the selected
Godot **4.7.2.stable.arch_linux.ed1daf0bf**. Afterwards, a **test-only** EditorPlugin
was added solely to that fixture to verify the ordinary graphical editor path.
This plugin is not part of Daydream's shipped output or installed into any game.

Using documented EditorInterface methods, that check:

1. Opened the script-free generated scene without playing the game; verified six
   cells and captured the actual 2D editor SubViewport.
2. Erased `(0,0)`, painted a cell at `(12,3)`, saved, reloaded and checked both edits.
3. Captured the edited viewport and wrote a report confirming script absence and
   preservation of the erased/painted cells.

Both viewport images were read and inspected: the initial cells were visible,
and the second capture showed the first cell removed and the new cell present.
The flat demonstration tiles establish placement/persistence, not polished art.
HOME/XDG config/data/cache for these editor subprocesses were confined to the
fixture. No existing editor, OpenCode installation or user project was patched.

The test initially attempted saving synchronously from a frame-post-draw callback,
which did not complete. Deferring the test edit/save to the idle phase and saving
without a preview thumbnail completed successfully. This was verification-helper
code only; the product serializer is headless and has no editor-time plugin.

## Limits

During the user's Potion Shop trial, a refusal toast disappeared before its exact
text could be captured. Read-only inspection confirmed an existing `hut_floor`
asset/index entry, but did not establish the actual refusal cause. No import was
retried and no Potion Shop file was modified by this investigation. Review errors
now additionally stay in a dialog until dismissal, with a regression checking
that the full message persists and no decision/import is automatically retried.

The user also identified binary/version questions as unnecessary friction. The
normal review flow now uses read-only engine discovery and checks project settings
or compatibility features before permissioned execution. Manual inputs are optional
advanced overrides, not required UI fields. Regression tests cover PATH/project
configuration selection, version conflicts, missing-engine errors, read-before-
resolve permission, execution refusal and real import without manual engine fields.
The full updated suite passed **156 tests**; dependency-free validation passed with
**58 optional tests skipped**. Read-only resolution in Potion Shop found
`/usr/bin/godot` and project target `4.7`; this discovery did not start Godot, retry
an import or modify the game.

The editor captures/transcripts are temporary machine-local artifacts, not checked-in
screenshots. The engine is a trusted executable, not sandboxed arbitrary code.
Only the tested Godot build is verified here; use the actual game's matching pin.
Manual Godot scene edits are preserved, but are not synchronized into staged JSON
or newly approved. There is no automatic merge or reverse import.
