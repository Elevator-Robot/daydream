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
inspection identifies `TileSetAtlasSource`, `Sprite2D`, `AnimatedSprite2D` and
`SpriteFrames` image references. Known `AtlasTexture`/`SpriteFrames` chains are
resolved only within the already-scanned, already-authorized documents, with
cycle detection and a 128-reference budget. No additional file is opened through
a reference. Budget exhaustion contributes to the visible unavailable count.
Images in sprite/tileset folders provide clearly labelled fallback evidence;
tilesets take priority. UI textures referenced only by TextureRect do not become
sprites unless they are deliberately placed in a sprite folder. No Godot code
is run and no frame layout or geometry is guessed.

Supported project sprites use a data-only Godot value reader to reconstruct
SpriteFrames clips with direct/AtlasTexture frames and static Sprite2D regions or
hframes/vframes grids. Catalog entries carry the exact scanned resource dependency
paths. Inspect/media operations declare and authorize those paths before parsing;
they never follow references into ungranted files. Composite content hashes include
the source image and resource bytes, so changed regions/timing invalidate media.
The native parser lives in `scripts/godot_sprite.py`. It uses bounded input,
nesting/token/reference limits, source-pixel and decoded-motion budgets, and PNG/APNG
output limits. Unsupported cropped-atlas chains, margins, mixed-size frames,
multi-sheet clips and ping-pong modes are not approximated. Clips use opaque media
keys rather than requiring Godot animation names to match Daydream naming rules.
The UI shares the normal animation cards, replay behavior and frame explorer while
retaining Project file status and hiding managed-review actions for native clips.
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
last snapshot. Compact comparison images retain matching window dimensions rather
than exposing pan/zoom controls. Motion replay, frame/tile selection, geometry, palettes, history
and feedback are read-only views.

Sprite cards consolidate linked animation assets rather than exposing a separate
animation collection category. The shared catalog resolves `sprite_groups` through
recorded base/frame hashes and animation edit ancestry, never by display name.
Missing-source animations stay visible as animated sprites. The sprite detail
section shows all latest linked clips together, with optional older versions,
looping, frame/timing inspection, feedback and source-set review commands.

Asset details fill the page instead of sharing the collection grid. A sticky
**Back to collection** control and Escape restore collection state and card focus.
The collection stays mounted to retain paging/scroll/filter state. SVG rendering
is used only for actual collision geometry, not a decorative icon set.

All dashboard selections use `dashboard/src/Select.tsx`, not direct Radix Content
instances. The shared wrapper uses bottom/start Popper placement, disables vertical
collision flipping, and bounds the list to the space below the trigger. Long menus
scroll instead of opening upwards. A trigger near the lower edge is scrolled into
a usable position before mouse/keyboard opening. Portal styling and accessible
Radix selection/keyboard behavior remain shared across status/terrain filters,
standalone clip controls and comparison selectors.

## Artwork gallery

The owner replaced the pan/zoom detail design with compact image and animation
galleries. `ImagePreview.tsx` displays native PNG/APNG images without gesture
capture, zoom controls or internal scrolling. Its one-shot replay lifecycle still
uses validated timing and leaves saved clips unchanged.

`SpriteAnimations` renders all clips from every latest linked animation set at
once. Older sets are optional; per-source loading/validation failures are displayed
instead of hiding the other sets. Each clip card keeps its own source identity,
timing, feedback and whole-source-set review command. Source/frame limits no longer
need to dictate the user-facing navigation. The removed canvas component and its
coordinate-helper tests are superseded by gallery/browser checks.

The selected candidate's information is always the same child element in its image
panel. Desktop single-image mode arranges that panel as artwork plus information
to its right; comparison stacks information below each image. A named View
Transition gently repositions the information where supported, with an immediate
fallback for unsupported browsers or reduced-motion preferences. Selected-first
order and review identity are preserved. Narrow layouts keep information below
the image in either mode.

Earlier canvas designs are historical, not current controls. Their evidence is
retained in the [canvas record](../validation/2026-11-08-asset-canvas.md) and
[gallery replacement record](../validation/2026-11-08-animation-gallery-and-budgets.md).

**Copy review command** carries a project-absolute `/assets` path, preventing another
project from silently resolving a same-named relative bundle. Approval and import
remain in the established TUI flow with fresh validation and separate confirmations.
