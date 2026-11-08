# Project dashboard reference

The owner approved the [design](PROJECT_DASHBOARD_DESIGN.md), React/Radix Themes
dependencies and session-owned loopback bridge on 2026-11-08. User instructions
are in [Project dashboard](../DASHBOARD.md).

## Shared read operations

- `dashboard.catalog`: combines managed asset/history discovery with project image
  discovery. Returns stable opaque entry/group IDs, saved times, review/import state
  and explicit scan-limit notices. Existing files are not automatically adopted.
- `dashboard.inspect`: validates a managed bundle or existing image and returns
  dimensions, palette where available, exact review/feedback/provenance information,
  frames, clip timing, tile/terrain/collision data, cells and artifact hashes.
- `dashboard.media`: returns validated, bounded PNG data. Managed animation motion
  retains its APNG bytes; thumbnails use the first source frame. Existing animated
  image files show their first frame, not inferred Godot clips.

These discoverable read-only operations use `scripts/dashboard.py` through the
shared CLI/native catalog. Preparation enumerates names before content reads and
resolves exact additional grants. Inspection/media reuse existing bundle validators.
The adapter never runs Godot, imports resources, prompts a model or writes approval.

Discovery excludes hidden/build/dependency folders and managed bundles already
represented in history. It is bounded to 3,000 directories / 1,000 project images,
alongside the existing 500-bundle catalog. Pagination is independent of those limits;
truncation produces a visible warning. Arbitrary Godot `.tres`/`.res`, audio and 3D
resource graph reconstruction is not implemented. Bounded `.tres`/`.tscn` text
inspection identifies direct `TileSetAtlasSource` references to project images;
images in tileset folders are also classified as atlas candidates. No Godot code
is run, no arbitrary reference recursion is performed, and no geometry is inferred.
Up to 500 such text resources are read using separately resolved exact file grants.
Unreadable/oversized resources contribute to the visible unavailable count.
SVG is inventoried without execution
or rasterization.

Existing image sources are bounded to 32 MiB / 16 megapixels; encoded media to
8 MiB. Thumbnails are at most 256 × 192 pixels. Existing-image palettes are exposed
when there are at most 128 colors. Runner output limits increase only for
`dashboard.catalog` (4 MiB) and `dashboard.media` (12 MiB including base64 overhead);
all other operations retain their 1 MiB limit.

## Session-owned browser transport

The TUI client starts `dashboard-bridge.js` only when the user opens the dashboard,
bound to `127.0.0.1` on an ephemeral port. It proxies reads through the existing
authenticated OpenCode client and `daydream.dashboard` RPC. This is not an installed
daemon or user service. Reopening a session/project reuses its endpoint; up to four
workspaces may be open per TUI.

Static UI assets contain no project data. API requests require a random per-workspace
capability, initially supplied in the URL fragment and sent as an Authorization
header. OpenCode credentials never enter the page. Strict Host, Origin and Fetch-Site
checks reject cross-origin/rebinding requests. CSP confines scripts/connections/media
to the local workspace and its blobs. Responses use no-store, no-referrer and nosniff;
there is no wildcard CORS.

Only GET catalog/inspect/media routes exist. Browser IDs resolve through the catalog
map; arbitrary path/project/session query parameters cannot replace the captured
project/session. Server calls verify that the session still belongs to that project.
Managed revisions are hash-bound from discovery; existing-image reads become
content-bound after the first successful read until refresh. Concurrent changes
produce a refresh-required error rather than mixing metadata and different pixels.

The client queues at most four reads; the bridge caps active reads at eight. Request
closure aborts upstream work. TUI cleanup aborts requests, destroys owned sockets and
closes listeners. A retained page reports disconnection and can be reopened through
`/assets`. This boundary is not an OS sandbox or protection against arbitrary code
running as the same local user.

The live OpenCode check exposed that its RPC validator disables regex patterns by
default. The RPC uses hash length bounds; the shared operation validator still
enforces the hexadecimal format. No validator policy was broadened.

## UI state, distribution and decisions

React 19 / Radix Themes 3 are built locally with esbuild and TypeScript. The stacked
Day / Dream wordmark uses bundled Press Start 2P, with its OFL notice included;
there is no font CDN. Decorative icons and promotional header text are removed.
Built JS/CSS
and third-party notices ship in `plugins/daydream-tools/dashboard-dist`; runtime
does not fetch a CDN or install packages. Source/build instructions are in
[Development](../DEVELOPMENT.md). Lockfile-pinned dependency notices and supplemental
provenance do not assign Daydream a project license.

Search/filter/selected-asset state survives browser reload using session storage.
Refresh updates the collection without silently switching a selected older revision;
the inspector offers **Open latest candidate**. Failed refresh keeps a visibly stale
last snapshot. Pixel comparison uses a shared integer scale, with Fit unavailable
while comparing. Motion controls, frame/tile selection, geometry, palettes, history
and feedback are read-only views.

Sprite cards consolidate linked animation assets rather than exposing a separate
animation collection category. The shared catalog resolves `sprite_groups` through
recorded base/frame hashes and animation edit ancestry, never by display name.
Missing-source animations stay visible as animated sprites. The sprite detail
section retains version/clip selection, looping, frame/timing inspection, comparison,
feedback and a separate animation review command.

Asset details fill the page instead of sharing the collection grid. A sticky
**Back to collection** control and Escape restore collection state and card focus.
The collection stays mounted to retain paging/scroll/filter state. SVG rendering
is used only for actual collision geometry, not a decorative icon set.

All dashboard selections use `dashboard/src/Select.tsx`, not direct Radix Content
instances. The shared wrapper uses bottom/start Popper placement, disables vertical
collision flipping, and bounds the list to the space below the trigger. Long menus
scroll instead of opening upwards. A trigger near the lower edge is scrolled into
a usable position before mouse/keyboard opening. Portal styling and accessible
Radix selection/keyboard behavior remain shared across filters, canvas controls,
animation versions/clips and comparison selectors.

## Artwork canvas

`dashboard/src/AssetCanvas.tsx` provides a DOM image viewport rather than flattening
APNGs into a raster canvas. It retains animation playback, source pixel scaling and
the existing preview-only replay lifecycle. The image plane is transformed around
the viewport center; Ctrl/Cmd+wheel and pinch zoom preserve the pointed source
coordinate. Unmodified wheel input scrolls the page and does not change scale.
Mouse/touch pointer capture supports panning, with global release cleanup. Bounds
are 1/256×–32×. Fit uses integer enlargement where possible, at most 8× initially;
large images can fit through fractional downscaling. ResizeObserver preserves Fit
on resize, while deliberate panning/zooming keeps the user's view.

Controls include Fit, 1:1, slider, zoom buttons, reset, background and an optional
source-pixel grid above 4×. Focused keyboard commands parallel the mouse controls;
Escape is left to collection navigation. Comparison keeps a fixed shared scale
rather than permitting inconsistent independent zoom. A compact metadata rail
sits beside the main viewport on desktop and below it on narrow screens. Zoom/pan
never modifies image bytes, source records, feedback or approval.

Artwork is no longer sticky within the overview grid: sticking that grid child
allowed it to cover the following animation section. Main viewports are capped
at 360 px high and animation viewports use 280 px. Pointer capture is released on
ending a drag, cancelled/uncaptured mouse movement clears dragging state, and window
blur clears all active drag pointers. No pointer-lock API is used.

**Copy review command** carries a project-absolute `/assets` path, preventing another
project from silently resolving a same-named relative bundle. Approval and import
remain in the established TUI flow with fresh validation and separate confirmations.
