# Sprite workflow — first vertical slice

Contributor/integration reference. User instructions are in [sprites and animations](SPRITE_WORKFLOW.md).

For the step-by-step user journey, see [the sprite workflow](SPRITE_WORKFLOW.md).
This document covers the static tool's formats, safeguards, and validation.

Scope: a single static, palette-limited sprite, non-destructive revisions, a real
image preview, explicit hash-bound approval, and preview-first import as a Godot
`Sprite2D` scene. No image API, model download, animation, tileset, daemon, editor
control, gameplay behavior, or automatic project launch is part of this slice.

The separate [animation extension](ANIMATIONS.md) now adds named clips, motion
previews, and animated Godot resources while preserving these static commands.

## Design

- Optional Pillow dependency, separate from the standard-library core.
- Editable source: versioned JSON with dimensions, up to 32 opaque palette colors,
  and pixel rows. `.` is transparent. Bounds: 1–256 pixels per dimension.
- Each revision is a new directory containing `source.json`, `sprite.png`, an
  8× nearest-neighbor checkerboard `preview.png`, and a hashed `manifest.json`.
  A `.gdignore` keeps revision/previews out of Godot's automatic import scan.
- Generation accepts an explicit pixel specification, not arbitrary code or a
  claim of general prompt-to-image generation. Existing PNGs can be converted to
  the editable source if their size, alpha, and palette meet the same limits.
- Edits create a fresh revision: recolor a palette symbol, mirror, paint pixels,
  or fill a rectangle. Originals and previous approval records are untouched.
- Approval is a separate explicit action tied to the complete revision digest,
  including the preview. It records the stated reviewer, not an authenticated
  identity or an automated art-quality judgment. The agent must obtain actual
  user approval; passing a command flag is not proof of human review.
- Import validates the approved revision again, plans new runtime PNG/scene and
  editable source files, and records provenance in the game's asset manifest.
  All asset destination collisions are refused. No existing scene, main-scene
  setting, texture import sidecar, or game script is overwritten.
- The generated standalone scene sets nearest texture filtering. It is not a
  playable character or automatic level placement. Godot import checks and
  graphical review remain separate, authorized steps.

All mutating commands preview unless `--apply` is supplied. Paths, file sizes,
schemas, and hashes are validated before writes. Symlinked managed files and
asset destination components are refused. Imports use an exclusive lock and
check the existing manifest before updating it; a failure may leave new output
files for inspection, never a destructive automatic rollback. This is not a
sandbox against a hostile process editing the same project concurrently.

## Acceptance criteria

- Create a transparent 32×32 slime with an explicit palette.
- Read the actual enlarged preview; distinguish preview inspection from a Godot
  screenshot or user art approval.
- Make a darker-outline revision without changing the original files.
- Refuse import before approval and after any approved-file tampering.
- Preview the import plan, apply into an isolated trusted Godot fixture, and
  verify resource import and scene startup with the existing bounded helper.
- Preserve existing assets, configuration, and unrelated manifest records.
- Record what remains for human art-direction and graphical review.

## Optional setup

From the permanent Daydream checkout:

```sh
python3 -m venv .venv-sprites
.venv-sprites/bin/python -m pip install -r requirements-sprites.txt
```

The normal installer and launcher do not install Pillow. The Python interpreter
running the sprite helper must have it; core coding/checking tools do not need it.
The agent uses this checkout-local environment when available. No runtime service
or paid provider is configured.

## Create and edit

The following examples use the default game layout; adjust paths to match the
game's rules. Start in the Daydream checkout and use a trusted existing game:

```sh
PY=.venv-sprites/bin/python
TOOL=scripts/sprites.py
GAME=/absolute/path/to/your/game
V1="$GAME/art/sprites/slime-v1"
V2="$GAME/art/sprites/slime-v2"

$PY "$TOOL" create examples/slime.sprite.json --output "$V1"          # preview
$PY "$TOOL" create examples/slime.sprite.json --output "$V1" --apply
$PY "$TOOL" edit "$V1" --patch examples/slime-darker-outline.edit.json --output "$V2"
$PY "$TOOL" edit "$V1" --patch examples/slime-darker-outline.edit.json --output "$V2" --apply
$PY "$TOOL" inspect "$V2"
```

Open the emitted `preview.png` with an image viewer. It uses a checkerboard only
for display; `sprite.png` retains true transparency. Source PNGs are not resized,
blurred, antialiased, quantized, or overwritten. Conversion of an existing sprite:

```sh
$PY "$TOOL" from-png /path/to/existing.png --name my_sprite --output "$GAME/art/sprites/my-sprite-v1"
# Inspect the plan; add --apply when authorized.
```

PNG conversion currently requires one frame, alpha 0/255, and 1–32 opaque colors.
Unsupported images fail explicitly rather than silently losing detail.
PNG metadata/color profiles are not copied; review the converted preview before
approving a new version. This workflow preserves explicit RGBA pixels, not all
external image-editor metadata or color-management settings.

### Source and edit formats

```json
{
  "schema_version": 1,
  "name": "gem",
  "width": 3,
  "height": 3,
  "palette": { "g": "#55c98a", "h": "#a6f1b7" },
  "pixels": [".g.", "ghg", ".g."]
}
```

Palette symbols are single ASCII letters/digits; `.` clears a pixel. Names are
lowercase asset slugs. Every row must have the declared width, and every symbol
must be declared. Files contain data, not executable drawing scripts.

```json
{
  "schema_version": 1,
  "operations": [
    { "op": "recolor", "symbol": "g", "color": "#26976d" },
    { "op": "mirror", "axis": "horizontal" },
    { "op": "paint", "x": 1, "y": 1, "symbol": "h" },
    { "op": "rect", "box": [0, 2, 2, 2], "symbol": "." }
  ]
}
```

Coordinates are zero-based; rectangle endpoints are inclusive. Patches contain
1–1024 operations. There is no resize, animation, arbitrary script execution, or
image-generation model in this initial implementation.

## Approval and import

Do not approve simply because generation/checks succeeded. Have the user inspect
the exact candidate, then copy its full `revision_hash` from `inspect`:

```sh
$PY "$TOOL" approve "$V2" --revision-hash HASH_FROM_INSPECT --reviewer user
$PY "$TOOL" approve "$V2" --revision-hash HASH_FROM_INSPECT --reviewer user --apply

# Initialize project metadata if not already present; preview before applying.
python3 scripts/init_project.py "$GAME"
python3 scripts/init_project.py "$GAME" --apply

$PY "$TOOL" import "$V2" "$GAME"          # inspect destination plan
$PY "$TOOL" import "$V2" "$GAME" --apply
```

By default this creates `assets/sprites/slime.png`,
`assets/sprites/slime.tscn`, and `art/sprites/slime.json`, using configured asset
and source roots. It appends a versioned sprite record to `.daydream/assets.json`,
preserving unrelated records and unknown root fields. Import checks only this
sprite type; it does not reinterpret other asset records. It does not run Godot.

Use `--destination path/relative/to/game` for a different runtime directory, or
`--name slime_v2` to add a new asset without replacing an existing one. The root
must already contain `project.godot` and valid project-local metadata. Asset
directory symlinks are refused even if they point elsewhere inside the project.

The approval binds `manifest.json`, editable source, PNG, and preview hashes.
Changing any of them requires a new revision and new approval. The record is
local audit data—not authenticated identity, a license grant, or a security
boundary against the user forging files. Unknown licensing stays `null`; no
project or asset license is chosen on the owner's behalf.

## Failure and recovery

- Existing revision directories, assets, scenes, and approval files are not
  overwritten. Existing texture import sidecars also reserve that asset name
  instead of being silently reused. Apply uses exclusive creation after preflight.
- On a partial failure, new files may remain unindexed. Inspect the reported
  plan and working tree before retrying; the helper will not delete originals or
  unrelated output to make an operation succeed.
- `.daydream/.sprites.lock` blocks cooperating concurrent imports. A crashed
  process may leave it behind; confirm the owning operation has stopped and
  inspect that exact lock before manually removing it. There is no blanket
  `--force` option. Detected concurrent metadata edits are not overwritten.
- The manifest update uses atomic replacement after a byte comparison. Editors
  which do not honor the lock can still race that final comparison; this is not
  a multi-file transaction or hostile-concurrency sandbox.

To undo an import, inspect its exact record in `.daydream/assets.json` and compare
the recorded hashes with the current PNG, scene, and source. Remove only the
unchanged files introduced by that import and that matching manifest record,
preserving all other records. If any output has since been edited, stop and keep
those edits rather than blindly deleting it. Revision bundles and approval
history need not be removed. There is intentionally no automatic destructive
undo command in this slice.

## Validation evidence and remaining work

Optional sprite tests run without touching a real game:

```sh
.venv-sprites/bin/python -m unittest discover -s tests -p 'test_sprites.py' -v
GODOT_BIN=/path/to/godot .venv-sprites/bin/python -m unittest discover -s tests -v
```

The initial slice was tested with Pillow 12.3.0 in an isolated test environment
and Godot 4.7.2. Checks cover palette/alpha/dimensions, non-destructive revisions,
approval tampering, collisions, symlink refusal, concurrent manifest changes,
and a real Godot import/startup. A fixture script also verifies that the imported
resource is a 32×32 `Sprite2D` using nearest filtering.

The actual 256×256 previews of the original slime and darker-outline revision
were read and compared. This is PNG evidence only. No user art approval or
graphical Godot result is claimed; those remain acceptance steps on a real game.
