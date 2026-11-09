# Existing project sprite discovery — 2026-11-09

## Report and diagnosis

The user reported that Wonderer appeared only under Project images, not Sprites.
Read-only inspection found an existing PNG sheet referenced through embedded
AtlasTexture/SpriteFrames data in the player scene. The dashboard had previously
classified existing image files only as generic images or tileset atlases.

## Reusable fix

The shared dashboard catalog now classifies project sprite images from:

- Direct Sprite2D texture references.
- AnimatedSprite2D/SpriteFrames references using embedded or external AtlasTexture
  resources within the already-scanned, already-authorized Godot text documents.
- `sprite` / `sprites` folders as explicitly labelled fallback evidence.
- Known registered sprite outputs when their staged source is unavailable.

Tileset references/folders take precedence over sprite folders. TextureRect-only
images outside sprite folders remain generic images. Each existing file keeps its
stable identity and project-image read path. The UI includes Project sprite in
Sprites and excludes it from the generic image filter, without adding a duplicate
card, adopting it as a managed revision or inventing approval.

The inspector identifies reference/folder evidence and resource locations. It
shows the original image/sheet; this change does not reconstruct native Godot clips
or guess frame geometry. The reference walker uses cycle detection and bounded
known relationships. It opens no unscanned reference files and executes no engine
or project script. Exhausted reference budgets produce visible unavailable counts.

## User-project verification

The actual shared catalog now reports `assets/sprites/wonderer-sprite-sheet.png`
as `collection_type: sprite`, with `sprite_evidence: godot_reference` and
`scenes/characters/player.tscn` as its resource reference. Its underlying kind stays
image, origin stays project, and state stays project_file. The project catalog
reported zero unavailable entries. No actual game file was modified.

## Validation

```sh
# dashboard/
npm run check
npm run build

# repository root
/tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -p test_dashboard.py -v
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

All **187 tests** passed in the optional Pillow/Godot/Node environment. The
dependency-free run passed with **85 optional skips**. Type checking, production
build and diff checks passed. New regression cases cover direct nodes, embedded
frame arrays, external scanned frame/atlas chains, folder fallback, tileset
priority, generic UI images, cycles, outside-path refusal and original-image bytes.

An actual Chromium dashboard fixture under `/tmp/opencode/daydream-project-sprites-*`
used only bundled sample artwork, with a synthetic Wonderer-shaped resource chain
outside a sprite folder. It verified that the sheet appears under Sprites with
Project sprite/Project file labels, loads its image and reference details, stays
out of generic Project images, and appears once under All artwork. File hashes
remained unchanged; no JavaScript exceptions occurred. The screenshot was opened
and visually inspected. The synthetic image is not the user's Wonderer artwork
and was not added to the README screenshots.

Existing documentation edits and README screenshots were preserved. No software
installation, user-configuration change, game import, approval, commit or push was
performed for this request.
