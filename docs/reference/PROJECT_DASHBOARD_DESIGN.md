# Project asset dashboard — proposed design

Status: architecture and project-local build dependencies approved by the owner
on 2026-11-08. Branch: `feat/project-asset-dashboard`, based on `2c20184`.
The bounded slice is implemented and has passed browser and live TUI checks;
user acceptance remains pending. See [implementation details](PROJECT_DASHBOARD.md).

## Product goal

A polished browser workspace that stays open beside Daydream. Browser reload or
an explicit Refresh action retrieves current project data without reopening the
dashboard from the terminal. The collection and selected asset are understandable
without remembering filenames, version suffixes or another agent prompt.

## User flow

1. Open `/assets` and choose **Open project dashboard**.
2. Browse the project's collection; search and filter by type, state and location.
3. Select artwork to inspect its details, playback, tiles, history and saved feedback.
4. Continue creation/review/approval/add/update through the existing guided Daydream
   flow. The dashboard explains the relevant next step and carries selected context
   where supported; it does not silently approve or import.
5. Keep the dashboard open while working. Refresh updates the collection and
   reports when a newer revision exists. Errors retain a visibly stale last snapshot
   instead of claiming the collection is current.

## Visual foundation

- React with Radix Themes for accessible, high-quality cards, tabs, menus, controls,
  dialogs and responsive layout. A dark, violet-accented Daydream theme emphasizes
  artwork, generous spacing and readable status information.
- A collection navigation area, searchable thumbnail workspace and detailed asset
  inspector. Useful counts come from actual project data; no decorative fake charts.
- Project-local development/build dependencies with pinned lockfile and retained
  third-party license notices. Ship built local browser assets with the plugin;
  normal users do not need npm, a dev server, external fonts or a runtime CDN.

## Collection and inspector scope

- Current candidates and retained history, grouped by kind and asset identity, with
  explicit Latest/Older labels, saved times and review/import status.
- Existing project artwork, clearly distinguished from Daydream-managed candidates.
  Display supported image formats and expose honest unsupported/unavailable states
  for resources that cannot be interpreted. Never infer approval from file presence.
- Sprites: pixel-exact preview, zoom/background controls, dimensions, palette where
  available, provenance, feedback and managed output locations.
- Animations: selectable clips, recurring preview-only playback, saved loop/FPS/
  duration/pivot information, frames/contact sheets and revision comparison.
- Tilesets: the complete validated tile collection, tile IDs/indices, terrain and
  collision filtering, a selected-tile inspector, atlas and placed-layout views,
  seam information and exact collision data where supplied by the source.
- Managed outputs: registered scene/resource paths and manual-edit status. Resource
  registration is not presented as proof of placement or runtime usage in the game.
- Pagination/lazy details and thumbnails replace the current 12-thumbnail overview.
  Discovery limits and unsupported files remain visible, not silently omitted while
  calling the results an exhaustive collection.

## Refresh architecture requiring review

The current browser viewer is a self-contained `file:` snapshot. Reloading it cannot
ask the shared backend for new data. The proposed dashboard adds:

1. A small HTTP bridge owned by the existing TUI plugin, bound only to
   `127.0.0.1` on an ephemeral port when the user opens the dashboard.
2. An unguessable per-dashboard capability plus strict host/origin checks and a
   restrictive CSP. Do not expose OpenCode credentials, arbitrary filesystem paths,
   unrestricted proxy requests or cross-origin access to the browser.
3. Project/session-bound read requests routed through the existing authenticated
   OpenCode client and permissioned native RPC/shared Python operations. Validation
   and discovery remain in reusable operations, not duplicated in the React app.
4. Fresh catalog/detail reads on refresh, with bounded image/file reads, no source
   execution for inspecting artwork, and explicit cancellation/error handling.
5. Lifecycle cleanup on TUI/plugin shutdown. This is a session-owned local listener,
   not an installed daemon, cloud service, account system or separately managed app.
   A disconnected dashboard explains how to reopen it through `/assets`.

The browser's data interface is read-only. Any handoff to a review command must
preserve the owning project/session and existing explicit decisions; it must not
turn asset inspection into an automatic generation, approval or import action.

## Validation and acceptance

- Test collection/type/history identities, supported existing-file discovery,
  source preservation, bounds, permission denials and invalid artifacts.
- Test bridge authentication, host/origin checks, project/session isolation,
  cancellation, shutdown and stale/disconnected responses in disposable fixtures.
- Verify a live refresh discovers a newly created revision and new project artwork
  while the same browser page stays open; retain selected context honestly.
- Inspect actual browser screenshots at desktop and side-panel widths and exercise
  search, filtering, tile selection, clip playback, history and refresh controls.
- Run the required Python/Node suites and isolated Godot fixture checks. Use only
  temporary installation/config destinations; no user project changes for testing.
- User acceptance of the dashboard is separate from existing P0/P1 acceptance.

## Sources

- [Radix Themes setup](https://www.radix-ui.com/themes/docs/overview/getting-started)
- [OpenCode V2 TUI APIs](https://opencode.ai/v2/docs/build/plugins/cli)
- [OpenCode V2 RPC](https://opencode.ai/v2/docs/build/plugins/rpc)
