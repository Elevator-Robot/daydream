# Create walls, floors and terrain

Daydream can help draw pixel-art floor and wall tiles, create matching edges and
corners, preview a small layout, and prepare it for Godot. Start with a small area
you can inspect before expanding it.

## Describe the look and purpose

For example:

> Create a mossy stone floor and low brick walls for a witch's garden. Match the
> game's palette and tile scale. Show a small layout with corners and transitions
> before adding it to the project. Name it Garden Walls.

Mention the intended view—top-down or side-on—along with reference artwork,
colors, tile size if you know it, and where the player should be blocked.
Daydream can help decide missing details; you don't need to write a tile specification.

## Inspect the candidate

Open **`/assets`**, select the tileset and open its preview. Check:

- Does it match the scale and style of the existing game?
- Do repeated tiles look natural, without distracting lines or patterns?
- Do corners, edges and transitions look right in the placed layout?
- Do collision outlines block the wall rather than walkable floor?

Yellow outlines show solid collision shapes; cyan shows one-way platforms.
See [collisions and platforms](COLLISIONS.md) for examples.

Ask for changes in ordinary language:

> The mortar is too bright. Darken it, soften the outside corners and keep the
> previous version so I can compare them.

Checking tile edges helps catch mistakes, but your visual judgment still matters.
Inspect the layout, not just one tile in isolation.

## Approve and add

1. Choose **Approve artwork** in `/assets` when the candidate is ready.
2. Choose **Add or update in project**.
3. For your first test, choose **Add a separate copy**. Daydream handles filenames.
4. Choose **Editor-visible cells** if you want to paint the layout directly in Godot.
5. Read the summary and separately confirm adding it.

The new scene is separate from your existing map. Open it in Godot or choose
**Preview this scene**. Ask Daydream to integrate it into your level only when
you are satisfied. Terrain layouts need Godot 4.3 or newer; keep your game's
expected engine version.

## Test with the player

Walk around walls, through doorways and over any ramps or platforms. Check that
the player's size fits openings and that the collision boundaries feel natural.
For a whole-game check, run **`/preview game`**.

## Current limits

The current workflow targets small rectangular pixel-art tiles. Animated tiles,
hexagonal/isometric terrain and automatic level design are not provided. Collision
shapes are deliberately authored; they are not automatically traced from the picture.

Next: [edit layouts in Godot](EDITOR_LAYOUTS.md) · [collisions](COLLISIONS.md) ·
[versions and updates](ASSET_LIFECYCLE.md).
