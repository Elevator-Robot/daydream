# Dashboard refinement from user feedback — 2026-11-08

## Requested changes

- Put animations inside their source sprite's details, not a separate category.
- Open full-page asset details with an obvious return path.
- Investigate missing project tilesets.
- Remove decorative icons and promotional workspace text; use a retro stacked
  **Day / Dream** wordmark.

## Implementation

The collection now offers All artwork, Sprites, Tilesets and Project images.
Recorded source/base/frame hashes and animation-edit ancestry associate managed
animation versions with sprite groups. Links do not rely on matching display
names. Linked animations are consolidated under the sprite, with clip/version
selection, looping, frame/timing inspection, comparison, feedback and a separate
animation review command. Animations whose source sprite is unavailable remain
visible as animated sprites rather than disappearing.

Asset details fill the page. A sticky Back to collection action and Escape return
to the mounted collection, retaining filters/paging/scroll and restoring card
focus. Decorative SVG icons and the requested workspace/tagline text are removed;
SVG is retained only to render actual collision geometry. The wordmark uses locally
bundled Press Start 2P with its upstream OFL notice, not an external font service.

Existing project atlas images can now appear under Tilesets, using bounded reads
of direct TileSetAtlasSource references in Godot text resources/scenes or a labelled
tileset-folder classification. This does not run Godot or infer unknown tile sizes,
terrain or collision metadata. The full semantic tile explorer remains available
for managed Daydream tilesets.

## Read-only user-project diagnosis

The Bound Souls catalog was inspected through the shared CLI without writes.
Its `assets/sprites/tilesets/tilesetppathway.png` had previously been classified
as a generic image. The updated catalog identifies its direct atlas reference
in `scenes/main/main.tscn`. Whisp's recorded animation base hashes link to its
sprite family; edited animation ancestry also retains those associations.
No project artwork, scenes or import settings were changed for this diagnosis.

## Automated and browser checks

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

Additional backend tests cover different-name sprite/animation associations through
edit ancestry, existing resource/folder atlas classification, no inferred tile
metadata and exact `.tres` read grants. The full optional suite passed **178 tests**,
including native Node and isolated Godot fixtures. The dependency-free suite passed
with **78 optional tests skipped**. Type checking, production build and
`git diff --check` passed; **175 local documentation links** resolved.

The synthetic dashboard browser fixture under `/tmp/opencode/daydream-dashboard-visual-*`
verified no separate animation category, no visible decorative SVGs, local retro
font loading, sprite-linked playback and source frame selection. Details measured
the full 1,440-pixel browser width with no visible library/sidebar. Back restored
card focus and the selected filter; Escape also returned. Both a referenced
existing atlas and the complete 162-tile managed set appeared under Tilesets.
The tile explorer remained usable at 600 pixels without horizontal page overflow.
No JavaScript exceptions occurred.

The actual isolated OpenCode TUI/RPC bridge check was rerun successfully after
these changes, retaining the catalog/detail/media permission boundary.

Actual collection, full-page sprite/animation, tileset-collection and narrow-detail
screenshots were opened and inspected. The sticky return path, unobscured animation
heading, retro title and absence of decorative icons were visible. Temporary
captures are machine-local evidence, not new artwork approval or gameplay acceptance.
