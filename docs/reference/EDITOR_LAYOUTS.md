# Editor-visible layout serialization reference

Contributor/integration reference. For everyday use, see [editing tile layouts in Godot](../EDITOR_LAYOUTS.md).

An approved tileset layout can now be imported as a **script-free TileMapLayer
scene with saved cells**, visible and editable in Godot before running the game.
The existing runtime-companion import is still available and unchanged. This does
not patch OpenCode/Godot, install an editor addon or control an existing editor.

## User flow

1. Create/edit the staged tileset and its `cells` through the shared tools. Review
   pixels, terrain, geometry and placement; approve the exact revision in
   `/assets` as usual. The layout is already included in that approval hash.
2. Choose **Add or update in project**. New copies use available filenames
   automatically, then offer **Editor-visible cells (script-free scene)**. Updates
   keep the selected managed asset's file layout; conversion from runtime to editor
   layout needs a separate copy. See [guided assets](ASSET_LIFECYCLE.md).
3. Choose **Prepare layout**. Daydream detects the project's configured Godot, or
   `GODOT_BIN`/Godot on PATH, and checks it against the project's engine target.
   Normal review does **not** ask for an executable path or version. A mismatch
   stops with a setup message; no upgrade or silent engine switch is performed.
4. Review the planned output paths and hash. Separately confirm apply.
5. Open the generated `.tscn` in your normal Godot editor. Cells are present before
   `_ready()`; paint/erase/save them normally. Instance the scene in the game only
   with explicit authorization. Existing maps/main scenes are not modified.

**Unlike ordinary filesystem-only import, this mode executes Godot even while
planning.** It creates only disposable generated scratch files until apply;
preview does not write the target project. Engine execution has its own
`daydream.engine.serialize` permission in addition to scoped reads and eventual
output edit permissions. Denial is not bypassed with a shell fallback.

## Native tool and CLI

`daydream_tileset_editor_import` / `tileset.editor_import` share the Python
implementation and require only `bundle`. Optional advanced `godot` and
`godot_version` overrides remain available without appearing in the normal UI. Other inputs
match ordinary import (`name`, `destination`, optional `revision_hash`/`plan_hash`,
and preview-default `apply`). `engine_timeout` is 1–30 seconds per process, default 20.

From the game directory:

```sh
daydream ops describe tileset.editor_import
daydream ops call tileset.editor_import --input \
  '{"bundle":"art/tiles/garden-walls-v1"}'
# After reviewing the plan, repeat with --apply and preferably its plan_hash.
```

Use the optional sprite interpreter if system Python lacks Pillow. The executable
must already be installed; no download, daemon or provider is added. Discovery
honors project `.daydream/preview.json` settings, then `GODOT_BIN`, then `godot`
(or `godot4` if `godot` is absent) on PATH. A deliberate advanced API override
can select another executable, but configured version constraints are not ignored.
The project's `config/features` supplies its compatibility target when no exact
pin is configured. An exact pin in project settings is honored; a compatibility
target such as `4.7` is not falsely treated as an exact patch pin. Unknown targets
still require the detected editor to be at least Godot 4.3; no project is upgraded.

If normal discovery cannot find a matching editor, configure it once through the
existing `.daydream/preview.json` mechanism (advanced setup), rather than answering
binary/version questions for every asset. Do not change a project's engine pin
merely to make import succeed.

The CLI invocation selects serialization execution. Native/UI adapters first ask
for project-file reads, then perform read-only `resolve` discovery, then require
execution grants for the resolved executable before even `--version`. Discovery
alone never starts Godot; a changed executable after resolution is refused unless
it is authorized. `prepare` only declares the request/read plan. Project settings
are never read behind a denied permission and no automatic permission is added.

## What gets saved

Editor mode writes four non-overwriting outputs: atlas PNG, `.tileset.tres`, the
standard engine-saved `.tscn`, and archived editable JSON. There is **no `.layout.gd`
companion or `@tool` script** in the imported scene. Tile atlas IDs, terrain and
collision resources remain the shared existing implementation, not a second pipeline.
The asset index retains hashes, source provenance and approval as before.

The scene carries generation metadata for the source revision, layout mode and
serializer version. This is provenance, **not proof a manually edited scene still
matches its original source/approval**.

## Preservation and boundaries

- Manual Godot edits belong to the imported scene. Nothing runs at `_ready()` to
  restore generated cells. Paint/erase edits survive normal save/reload and play.
- Add-copy selects unused paths and preserves existing files/sidecars. Explicit
  managed updates keep stable paths only if every registered file still matches
  its hash, and archive previous bytes before replacement. A manually edited scene
  is protected: add a separate copy and deliberately integrate it. No automatic
  merge is provided, and unsaved editor buffers cannot be detected.
- Editing the staged source layout requires a fresh revision and approval. Godot
  painting does not automatically synchronize back to source JSON or approve a new
  generated revision. Reverse-import/round-trip source editing is not implemented.
- The actual game is not launched during serialization. A generated scratch project
  receives only validated pixels, our resource text and a fixed serializer helper;
  user autoloads, addons, GDExtensions, main scenes and project settings are not copied.
  HOME/XDG settings/data/cache are redirected to scratch locations for the subprocess.
- The executable is still real local code: this isolation is **not an OS sandbox**.
  Trust the chosen binary. Output/time are bounded, owned process groups are cleaned
  up on cancellation/failure, and existing files are never destructively rolled back.
- A failed apply can leave partial new output. Inspect before retrying. A changed
  revision, metadata/index, serializer output or destination invalidates the exact
  import plan; no automatic retry changes the reviewed plan.
- Generated scene formats follow the selected engine. Import/open with the game's
  matching engine; this is not a cross-version scene converter. Current verification
  uses Godot 4.7.2; other versions can refuse unsupported serializer structures safely.

## How serialization stays clean

Godot's documented `TileMapLayer.set_cell`, `PackedScene.pack` and
`ResourceSaver.save` create the scene. Python never writes or decodes the private
tile-map byte layout. Two instances are checked before entering the scene tree,
including one in a fresh Godot process after deterministic scene-local ID labeling.

Godot generates random external-resource labels/node tracking IDs. Only those
documented labels in our fresh one-node scene are stabilized; no existing user
file is normalized. Engine-produced tile data and the saved format are untouched.
Godot then reloads the result and checks every source/atlas coordinate and absence
of a script. Identical inputs/pin produce identical planned bytes on the tested
engine, so the existing exact-content plan hash can be enforced during apply.

References: [PackedScene](https://docs.godotengine.org/en/stable/classes/class_packedscene.html),
[ResourceSaver](https://docs.godotengine.org/en/stable/classes/class_resourcesaver.html),
and [documented TSCN labels](https://docs.godotengine.org/en/stable/engine_details/file_formats/tscn.html).

## Validation

Tests cover engine permission refusal before execution, process timeout/output
limits, deterministic plans, version/stale-plan refusal, script-free cells before
`_ready()`, manual save/reload without resetting cells, collision resources and
non-overwriting imports. The target-fixture autoload is deliberately invalid to
detect accidental opening of game code by the serializer.

A separate actual graphical Godot editor check opened the generated scene before
playing, captured visible cells, erased/painted a cell, saved/reopened, and captured
the persisted result. Its test-only editor plugin was confined to the disposable
fixture; no addon is shipped or installed by this capability. See the
[dated validation](../validation/2026-11-07-editor-layouts.md).
