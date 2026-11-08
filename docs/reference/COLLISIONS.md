# Collision geometry and export reference

Contributor/integration reference. For everyday use, see [walls, ramps and platforms](../COLLISIONS.md).

Daydream supports **explicit convex polygons** in the shared tileset workflow:
create/edit → inspect/preview → exact approval → separate Godot import.
Existing `solid:true/false` tiles remain valid and are not rewritten or migrated.

## Quick start

> Give this tile a ramp rising to the right. Make that ledge a one-way platform.
> Show me collision coverage and coordinates before approving or importing.

```sh
daydream ops call tileset.edit --input-file /path/to/daydream/examples/slopes.collision-edit.json
# Review the plan; repeat with --apply to create the staged revision.
```

Use the sprite environment's Python if system Python lacks Pillow. The example
assumes the existing garden-wall revision and edits geometry only, not artwork.
Then use `/assets art/tiles/garden-walls-collisions-v2`; approval and import
remain separate. Existing scenes, character controllers and engine pins stay untouched.

## Presets and custom geometry

A `tileset.edit` tile change chooses one `collision_preset`:

```json
{
  "bundle": "art/tiles/platforms-v1",
  "tiles": [
    {"id": "ramp", "collision_preset": {"preset": "slope_up_right"}},
    {"id": "ledge", "collision_preset": {
      "preset": "platform", "thickness": 2,
      "one_way": true, "one_way_margin": 1
    }}
  ],
  "output": "art/tiles/platforms-v2"
}
```

| Preset | Geometry |
| --- | --- |
| `none` | No polygons; no extra settings |
| `full` | Full tile rectangle |
| `slope_up_right` | Solid triangle below a surface rising bottom-left to top-right |
| `slope_up_left` | Solid triangle below a surface rising bottom-right to top-left |
| `platform` | Top horizontal band; default thickness 1 pixel and one-way enabled |

Other presets default to two-way collisions. Nonempty presets accept `one_way`
and `one_way_margin`; only `platform` accepts `thickness`. Presets expand into
canonical polygons, so the revision hash covers actual points/settings.

For custom pieces, source tiles and edits accept `collisions`:

```json
{
  "id": "split-wall",
  "collisions": [
    {"points": [[0, 0.5], [4, 0], [4, 16], [0, 16]]},
    {"points": [[12, 0], [16, 0], [16, 16], [12, 16]], "one_way": false}
  ]
}
```

This 16×16 example leaves a passable middle gap. Rules:

- Coordinates are **tile-local pixels, top-left origin**, X right/Y down, on a
  **half-pixel grid**, inclusive of `(width,height)`. Export converts to Godot's
  centered tile coordinates without offsetting artwork.
- Up to **8 polygons/tile**, **3–16 distinct vertices/polygon**, either winding.
  Shapes must be simple, strictly convex and nonzero-area. Omit the repeated
  closing vertex and collinear intermediate points. Split concave shapes into
  convex pieces; there is no automatic decomposition or alpha tracing.
- Nonfinite/out-of-tile/off-grid coordinates, booleans, intersecting edges,
  malformed points and unknown fields are refused. Pieces may overlap intentionally;
  they are not automatically unioned, and holes mean omitted geometry.
- `one_way` defaults false. `one_way_margin` defaults to 1 pixel and is finite 0–16.
  Platform thickness is .5 pixels through the tile height, on the half-pixel grid.
- Canonical source tiles with `collisions` require **`solid:false`**. An empty list
  disables collisions. An edit chooses only one of `solid`, `collisions` or
  `collision_preset`; explicit `solid` switches back to legacy behavior in the new
  revision and removes its custom polygons. The parent is preserved.

## Review, compatibility and limits

Yellow outlines show two-way/solid geometry; cyan shows one-way geometry. New
geometry bundles include hash-bound `collisions.png` placed-layout coverage,
artwork-only `layout.png`, the numbered tile preview and exact coordinates/settings
in the browser. Raster overlays approximate half-pixel geometry at tile-pixel
resolution; the numeric listing is authoritative. Geometry is not inferred from alpha.

`tileset.inspect` reports polygon/one-way counts, coordinate/legend metadata and
the overlay path. Changing vertices, one-way flags or margins creates a fresh
unapproved revision. Old approval and import-plan hashes cannot authorize it.
The existing `/assets` approval and feedback safeguards apply unchanged.

Legacy bundles without `collisions` keep their original artifact set, preview/viewer
behavior, hash and approval identity. No overlay is retroactively added. The
optional source field is an additive version-1 extension. Godot 4.3+ export uses
the existing physics layer/mask and per-polygon points, one-way flags and margins.
Import does not launch Godot or require an addon/package.

One-way blocking uses Godot's local upward direction, not a custom per-edge normal.
Controller speed, rotation, floor handling and margins affect play feel: test with
the actual game. This does not add a character controller, freehand vertex editor,
navigation, automatic slope artwork or arbitrary concave-polygon support.

Tests cover geometry bounds/presets, invalid polygons, compatibility, native grants,
immutable edits, tampered overlays and fresh approval. Real Godot checks verify
polygon counts/half-pixel coordinates, ramp ray positions/normals, a passable gap,
legacy full/empty tiles, and a `CharacterBody2D` passing upward through a one-way
platform and landing from above. These synthetic checks are not human game acceptance.

See [tilesets](TILESETS.md), [review](REVIEW.md), and Godot's
[TileData API](https://docs.godotengine.org/en/stable/classes/class_tiledata.html).

## Manual test checklist

Use a **new disposable Godot project**, not the main game. Restart OpenCode so
the native tool schemas/TUI are current. Pillow must already be enabled; select
the intended installed Godot 4.3+ binary without upgrading or migrating an engine.

Suggested Daydream prompt:

> Create a small disposable collision test project here using the shared native
> tileset tools. Include a floor, left- and right-rising ramps, a two-piece tile
> with a passable middle gap, a no-collision tile, and a thin one-way platform.
> Add a simple movable character with left/right/jump controls and an obvious
> visual indication of where each test is. Do not change other projects or install
> dependencies. Show collision previews before import; I will approve the exact
> revision through /assets. Do not self-approve or import before that.

The character/room are ordinary game code for this disposable project, not a new
automatic level-generation or controller capability in the tile pipeline.

1. **Review:** `/assets` → select the tileset. Check both ramps, the gap,
   the thin platform and the collision-free tile. Yellow is solid; cyan is one-way.
   Expand exact geometry to inspect vertices, flags and margins. Raster overlays
   approximate half-pixel positions, so compare the numeric data too.
2. **Approve separately:** approve the exact revision. Confirm this alone adds no
   runtime asset files. Then select **Review import plan**, check destinations,
   and explicitly apply. Existing files must not be silently replaced.
3. **Play:** `/preview game`. Walk both directions over both ramps. Jump through
   the platform from below, then land from above. Check the gap is passable with
   a character narrow enough to fit, the empty tile does not block, and ordinary
   solid floor tiles do block. Use Godot's collision-debug display if needed.
4. **Revise:** request a collision-only change (for example platform thickness or
   a polygon vertex). Confirm it creates a new unapproved revision, preserves its
   parent, and cannot import with the old approval. Review/approve it anew; choose
   a new import name or destination rather than overwrite earlier output. To test
   the revision in game, explicitly agree which test-room reference to update.
5. **Finish:** `/preview status` for diagnostics, then `/preview stop`. Save notes
   or captures with the Godot version, revision hash, controller settings and exact
   steps for any snagging, fall-through or unexpected blocking. Passing fixture
   tests does not replace this controller-specific check.

One-way behavior is upward-oriented in the tile's local coordinates. Slope floor
angles, floor snapping, motion speed, character shape and one-way margins affect
results. Report those details instead of changing engine versions or adding an
unrelated physics workaround to make a failed check disappear.
