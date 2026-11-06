# Environment art: floors, walls and terrain

Daydream extends its editable sprite engine to environment tilesets. Use shared
`tileset.*` operations, not separate per-game atlas or collision generators.
This is bounded pixel art, not general AI image generation or automatic level design.
Nothing in an existing game is regenerated automatically.

## Workflow

> Make matching grass and brick seed tiles, generate their transitions and corners,
> and show me a tiled layout and collision coverage before importing anything.

1. Draw/ingest seeds with `sprite.create`, `sprite.from_png` and `sprite.edit`.
   Agree on palette, scale, material style and collision intent first.
2. `tileset.transitions` generates **162** combinations: two center terrains and
   all floor/wall/empty corner assignments. This includes empty-map boundaries.
3. `tileset.inspect` validates artwork, exact boundary pixels, layout corners,
   terrain coverage, and artifacts. Review the layout with `/preview asset`.
4. `tileset.edit` revises pixels, global colors, terrain assignments, collision
   polygons/slopes/one-way settings, legacy solid flags, bitmasks and cell placement
   in a fresh revision. See [richer collisions](COLLISIONS.md).
5. Use `/asset-review` to explicitly approve the exact candidate or request changes,
   then review and confirm import separately. Authorized CLI `tileset.approve`
   remains a fallback. Model-facing tools cannot write approval decisions.
6. Deliberately instance the new layer or use its TileSet in an existing layer,
   then run `/preview game` and playtest. Import does not edit existing scenes.

`tileset.create` also accepts explicit canonical tile specifications without seed
generation. All common actions have native `daydream_tileset_*` tools, with schemas
available through `daydream_describe` and the CLI. Python implementations are shared.

## CLI example

From the checkout, using an already-enabled Pillow environment and a trusted game:

```sh
# Preview the seed writes first; repeat with --apply only after reviewing the plan.
.venv-sprites/bin/python scripts/sprites.py create examples/floor.sprite.json \
  --output /path/to/game/art/tiles/floor-v1
.venv-sprites/bin/python scripts/sprites.py create examples/wall.sprite.json \
  --output /path/to/game/art/tiles/wall-v1

# After writing those seeds, preview generation; repeat with --apply to write it.
.venv-sprites/bin/python scripts/operations.py --project /path/to/game \
  call tileset.transitions --input-file examples/walls.transitions.json
.venv-sprites/bin/python scripts/operations.py --project /path/to/game \
  call tileset.inspect --input '{"bundle":"art/tiles/garden-walls-v1"}'
```

After human review and explicit authorization to record approval, from the game
directory (use the sprite interpreter if system Python lacks Pillow):

```sh
daydream ops call tileset.approve --input \
  '{"bundle":"art/tiles/garden-walls-v1","revision_hash":"EXACT_HASH_FROM_INSPECT","reviewer":"YOUR_LABEL"}' --apply
daydream ops call tileset.import --input '{"bundle":"art/tiles/garden-walls-v1"}'
# Review the import plan, then repeat the import command with --apply.
```

Import requires initialized `.daydream` metadata (`project.init` previews by default).
No software, project metadata, main scene or engine version is changed automatically.

## Source, edits and limits

Canonical version-1 source contains exactly:

- `schema_version`, lowercase `name`, and 1–8 distinct `terrains` name slugs.
- `tiles`: 1–192 entries with `id`, standard sprite `source`, center `terrain`,
  four `corners` and Boolean `solid`. IDs are unique; canvas/palette mappings match.
  Optional `collisions` adds up to eight convex polygons with `solid:false`;
  presets are available in tile edits. Legacy solid flags retain their old behavior.
- Corner order: **top-left, top-right, bottom-right, bottom-left**. Values index
  `terrains`; `-1` means empty. Center terrain must be nonempty.
- `cells`: up to 1,024 `{x, y, tile}` placements in a 64×64 grid, with no overlaps.
- Unsigned 32-bit `collision_layer` and `collision_mask` bitmasks.

Custom tiles are 2–64 pixels per side; generated transition seeds are 4–32. Source
JSON is limited to 1 MiB and the whole revision to 24 MiB. Seeds must have equal
opposite RGBA boundaries and share a canvas/palette. Generation combines their
pixels using deterministic corner/center masks; it does **not** invent shading,
mortar, texture detail or art direction. Refine seeds or generated tiles as needed.

Edits accept up to 64 named tile changes per call. Use `tiles: []` for layout-only,
global `recolor` or bitmask edits. Tile patches use the existing sprite patch format.
Recolor all tiles globally when changing a shared palette; tile-local palette
divergence is rejected. Changing art, corners, layout or collision data invalidates
the previous approval. Parents and their approvals are preserved.

## Review evidence

Bundles contain editable `source.json`, `atlas.png`, numbered `preview.png`,
`layout.png`, `seams.json`, local `preview.html`, a hash manifest and `.gdignore`.
Yellow outlines mark **solid collision geometry** (full rectangles for legacy
solid tiles); cyan marks one-way polygons. Explicit geometry adds `collisions.png`
layout coverage and exact point/settings listings. Geometry is not alpha tracing.
The entire bundle and collision/layout metadata are bound to the approval hash.

Inspection compares exact RGBA boundaries of terrain-compatible pairs and checks
corner agreement in placed neighboring cells. Coverage includes missing corner
patterns, with a full count and bounded examples. Generated two-terrain families
include every center/corner/empty combination; custom subsets may have paint gaps.
Import refuses mismatched compatible edges or contradictory layout corners.

This is a conservative edge contract, not proof of perceptual seamlessness,
pleasant repetition, suitable collisions or playability. Review the result in the
browser and graphical Godot. Synthetic fixture approval is not user art approval.

## Godot output and boundaries

Targets **Godot 4.3+** (`TileMapLayer`). Keep the game's own engine pin. Import
writes a nearest-filtered atlas, `.tileset.tres` with `TileSetAtlasSource`,
**match-corners** terrain metadata, a physics layer, a reusable `TileMapLayer`
scene, deterministic `.layout.gd` companion and archived editable JSON. Default
destinations are the configured roots plus `/tilesets`. Provenance and approval
are retained in `.daydream/assets.json`. Existing files, sidecars, symlinks and
metadata conflicts are refused; interrupted partial output is never overwritten.

The TileSet is paintable in the editor. The example layout is populated **at
runtime** via documented `set_cell()` calls, not baked into editor cell data.
The companion is not `@tool`; it runs no editor-time code. This avoids undocumented
binary serialization. Instance the layer deliberately; existing maps stay untouched.
All collisions require human judgment, especially on partly transparent transition
tiles. [Convex polygons, slopes and one-way platforms](COLLISIONS.md) are supported;
animated tiles, hex/isometric terrain, navigation, automatic level design and image
providers remain outside this slice.

Tests cover bounds, coverage, seams, permission grants, preview/apply, CLI discovery,
immutable edits, exact approval, tampering and safe import. Real Godot checks load
the atlas, verify terrain/collision metadata, paint onto empty cells, populate the
layer and check an actual physics ray hit. Browser-viewer tests cover tiles too.
These synthetic checks are not real-game art/play-feel acceptance.

References: Godot [TileSet](https://docs.godotengine.org/en/stable/classes/class_tileset.html),
[TileData](https://docs.godotengine.org/en/stable/classes/class_tiledata.html) and
[TileMapLayer](https://docs.godotengine.org/en/stable/classes/class_tilemaplayer.html).
Real resource checks currently use Godot 4.7.2.

A graphical synthetic garden-wall fixture was also rendered and its actual Godot
viewport capture and numbered contact sheet inspected. Tile placement, pixel-scale
rendering and the simple masked transition shapes were visible. This validates
the pipeline, not polished environment art: the example's geometric brick edges
are provisional and still need human art-direction/collision approval.
