# Persistent project dashboard — 2026-11-08

## Authorization and scope

The user requested a new branch and a high-quality UI framework for a persistent
project asset workspace. They explicitly approved React/Radix Themes, project-local
UI build dependencies and the read-only, session-owned loopback bridge described
in [the design](../reference/PROJECT_DASHBOARD_DESIGN.md).

The implementation lives on `feat/project-asset-dashboard`, based on `2c20184`.
It adds a real refreshable browser collection rather than another static overview.
Supported existing project images are included alongside managed candidates.
Arbitrary Godot resource graphs, audio and 3D interpretation remain outside this
slice; unsupported previews and scan limits are visible.

## Automated checks

Commands used:

```sh
# From dashboard/:
npm install --ignore-scripts --no-audit --no-fund
npm run check
npm run build

# From the repository root:
/tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -p test_dashboard.py -v
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

Type checking and production bundling passed. The optional full suite passed
**175 tests**, including Node transport/UI-service suites and isolated Godot checks.
The dependency-free suite passed with **75 optional tests skipped**.

New checks cover project-image discovery and exclusions, managed history/identity,
exact read grants, source preservation, stale/corrupt media, SVG non-execution and
bounded scans. Transport checks cover capability authentication, Host/Origin
rejection, read-only methods, arbitrary-path rejection, project-image hash binding,
catalog replacement, session separation, request cancellation and listener cleanup.

## Actual browser experience

An isolated synthetic Moonlight Workshop project under
`/tmp/opencode/daydream-dashboard-visual-*` used repository example artwork to build
colored sprites, a multi-frame animation and a 162-tile terrain set, with retained
history, feedback, one registered import and existing project images.

The real bridge and Python operations served the built React/Radix application to
isolated Chromium. Checks exercised:

- Thumbnail collection, text search, asset-type filters and history visibility.
- All 162 tiles, selected-tile details and atlas cropping.
- Animation inspector, timing/loop controls, source frames, contact sheets and
  palette/feedback data. The copied review command retained the project-absolute path.
- Refresh with a new project image and an added animation revision. The previously
  selected version stayed selected and gained an **Open latest candidate** action.
- Browser reload retained selection. The 600-pixel side-window layout showed a
  usable inspector without horizontal page overflow.
- Closing the owned bridge caused an explicit disconnected/stale-snapshot message.
- No JavaScript exceptions or HTTP(S) requests to external origins occurred.

Actual collection, tileset, animation and narrow-layout screenshots were opened and
visually inspected. Initial tiny thumbnails were corrected to readable, pixelated
card previews. The selected tile's scaling was aligned with its geometry overlay.
Captures are temporary machine-local evidence, not a human artwork approval.

## Actual OpenCode integration

A standalone OpenCode TUI used temporary install/config/data/cache under
`/tmp/opencode/daydream-dashboard-tui-*`. The fixture dispatched `/assets`' registered
command; keyboard input selected **Open project dashboard**. A test-only opener
captured its URL instead of altering or controlling the user's browser.

Reads then traversed the actual client-owned loopback bridge, OpenCode RPC,
permission checks and native Python backend. The catalog returned 17 entries;
adding a synthetic project image and refreshing returned 18. The inspector returned
all 162 tiles and valid atlas media. All 82 pre-existing revision files kept their
hashes. No model execution, approval, import or game launch occurred.

This test caught an RPC-schema incompatibility: OpenCode disables regex patterns
in RPC schemas by default. The public hash field now uses length bounds while the
shared Python validator retains exact hash validation; no policy was widened.

## Distribution and limits

Built JS/CSS and extracted third-party notices are included with the standard plugin.
The package lock pins dependencies; installation scripts never run npm. One missing
upstream package notice is preserved with provenance under `dashboard/third-party/`.
No license was selected for Daydream itself.

The dashboard is read-only and ends with its owning TUI/plugin. Refresh is explicit,
not a filesystem watcher or guaranteed live update stream. Copying a review command
hands the selected project-absolute candidate back to the existing TUI review flow.
User acceptance and merge were not performed by these checks. The owner later
authorized commit/push and PR creation on 2026-11-08.

## Final branch publication checks

After the user-directed refinements, the final optional suite passed **178 tests**
and the dependency-free run passed with **78 optional skips**. Type checking and
production build passed. The final browser run also checked downward dropdown
placement, scrolling lists near the viewport edge and the Elevator Robot footer
link, alongside the compact canvas and collection tests. The live TUI/RPC check
was rerun successfully. Bundled dependency notices are retained in `licenses.txt`,
with a reference in the JS bundle; generated notice whitespace is normalized for
clean diffs without removing the notice text.
The generated JS is marked as generated and exempt from source whitespace checks:
bundled dependency CSS template strings contain whitespace that is deliberately
preserved rather than rewritten inside JavaScript string literals.
