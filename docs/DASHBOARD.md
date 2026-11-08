# Keep your project collection beside you

The project dashboard is a browser workspace for your artwork. Keep it open while
Daydream creates or revises assets, then refresh to see what changed.

## 1. Open your workspace

1. Open Daydream in your game project.
2. Run **`/assets` → Open project dashboard**.
3. Keep the browser beside your chat or Godot editor. Allow any requested project
   reads in Daydream so the collection and previews can load.

The dashboard is included in the standard installation. You do not need to install
a web framework, run a development server, or create an account.

## 2. Find artwork

- Choose **All artwork**, **Sprites**, **Tilesets**, or **Project images**.
- Search by name or location and filter by review status.
- Enable **History** to include older revisions. **Latest** and **Older** labels
  distinguish versions; same-named sprites and animations have separate histories.
- Use **Previous / Next** at the bottom to browse larger collections.

Dropdowns consistently open below their controls. Long lists scroll; controls near
the bottom move into view before opening so the choices remain reachable.

Daydream candidates appear alongside supported existing images in the project.
**Project file** means existing artwork, not an approved Daydream candidate. Registered
output textures are linked to their managed asset rather than counted twice.
Managed previews show the staged candidate; manually edited project outputs may
differ. Their status and locations appear in the inspector. A different imported
revision is labelled explicitly.

## 3. Inspect an asset

Click a card to open full-page asset details. **Back to collection** stays visible
while you scroll; **Escape** also returns. Your filters, page and collection scroll
position are kept, and keyboard focus returns to the card you opened.

### Sprites and existing images

Inspect the artwork, dimensions, palette where available, saved time and status.
The artwork now sits in a pan-and-zoom canvas, beside a compact information panel:

1. Scroll normally to move the page. Hold **Ctrl** (or **Cmd**) while scrolling over
   the canvas to zoom around the point you're inspecting; pinch also zooms.
2. **Drag** to pan the image, including when zoomed beyond the visible canvas.
3. Choose **Fit** or double-click to center the whole image. **1:1** shows native pixels.
4. Use the zoom slider or **+ / −** for precise changes. **Reset view** recenters it.
5. Switch between checkerboard, dark and light backgrounds, or enable **Pixel grid**
   to inspect pixel boundaries at 400% zoom and above.

With the canvas focused, **+ / −** zoom, arrow keys pan, **F / 0** fit, and **1**
returns to native pixels. **Escape** still returns to the collection.
On narrow screens, the information panel moves below the canvas. Sprite and
animation canvases are compact and stay in normal page flow, so they never stick
over one another as you scroll.
Preview panels are capped at a comfortable width rather than stretched across
large monitors; the detail content is centered and remains responsive.

**Details** contains source
locations, content identity, provenance and managed output information where available.

### Animations

Animations live **inside their sprite's details**, not in a separate collection
category. Sprite cards show a linked-animation count. Open the sprite and choose
**View animations**, or scroll to its **Animations** section.

1. Choose an animation version, then a clip to watch it.
2. Check FPS, duration and the saved loop behavior.
3. Leave **Loop preview** on to repeatedly inspect one-shot clips, or turn it off
   to follow their saved settings. **Replay** starts again.
4. Expand **Inspect animation frames, timing and pivot** to inspect source frames,
   timelines and contact sheets
   with timing and pivot markers. Use **Actual size** to read a large sheet without shrinking it.
5. Turn on **Compare earlier animation** to review an earlier version alongside
   the selected animation at the same pixel scale.

Preview controls do not change the saved animation or gameplay.
Animation previews use the same pan-and-zoom canvas. While comparing versions,
the shared scale selector keeps both sides at the same pixel scale; each can be panned.
Animation links follow recorded source revisions, not matching names. If the
source sprite is missing or cannot be linked, the animated asset remains visible
under **Sprites** rather than being hidden. Existing arbitrary Godot SpriteFrames
resources are not automatically reconstructed by this dashboard.

### Tilesets

1. In **Overview**, choose the placed layout, complete atlas or available collision coverage.
2. Open **Tiles** to browse the entire validated tileset.
3. Filter by terrain, blocking/one-way geometry or tile ID.
4. Select a tile to see its enlarged artwork, terrain corners, collision overlay
   and exact polygon settings where present.

Existing project atlases now appear under **Tilesets** too: the dashboard checks
direct atlas-image references in Godot text scenes/resources and images stored in
`tilesets`, `tileset` or `tilemaps` folders. Open one to inspect the complete atlas
and see where it was referenced. Folder-based candidates are labelled as such.

The tile-by-tile explorer uses Daydream metadata. For existing atlas images, tile
sizes, terrain and collision rules are not guessed from pixels or reconstructed
from arbitrary Godot resource graphs. If Tilesets is empty, check that you opened
the intended project, clear filters and refresh; discovery limits are shown.
The placed layout is the candidate's saved layout; manual painting in a Godot
scene does not synchronize back into that source view.

### Versions and feedback

**History** lists retained versions, newest saved first. Selecting one changes what
you inspect, not which artwork is approved or installed. **Open latest candidate**
returns you to the newest saved version. Review notes and recorded approval are
shown when present.

## 4. Refresh while you work

Click **Refresh collection**, or reload the browser page, after changes in chat or
the editor. Search/filter choices and the selected asset are retained. If a newer
candidate exists, your selected version is clearly marked **Older** instead of
silently switching the artwork you were inspecting.

Keep the Daydream terminal open. Closing or reloading its plugin disconnects the
dashboard; reopen it through `/assets` to reconnect. If refresh fails, the previous
snapshot stays visible with a warning that it may be stale.

## 5. Continue the guided asset flow

For a Daydream candidate, click **Copy review command**, then paste it into your
project's Daydream session. The command already identifies the selected asset.
Continue **review/revise → approve → add/update → preview** there.

The dashboard itself is read-only: browsing, refreshing, comparing and looping
previews never approve artwork, update game files or start a model request.

## Collection coverage

The dashboard includes Daydream revisions and supported project images: PNG, JPEG,
WebP, GIF, BMP and TGA. SVG files are listed with a clear unsupported-preview message.
Animated project image files show their first frame; full clip controls use managed
Daydream animation data. Hidden/build folders are excluded. A visible notice tells
you when a discovery or image-size limit prevents a complete view.

Next: [Your assets](REVIEW.md) · [Versions and updates](ASSET_LIFECYCLE.md) ·
[Preview and playtest](PREVIEW.md).
