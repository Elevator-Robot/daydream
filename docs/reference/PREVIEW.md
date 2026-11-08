# Preview implementation and advanced configuration

Contributor/integration reference. For everyday use, see [previewing your game](../PREVIEW.md).

The standard Daydream plugin includes a native OpenCode TUI command:

```text
/preview                         Choose Game, Asset, Status, or Stop
/preview game                    Run the configured main scene in Godot
/preview asset                   Browse sprite/animation/tileset revision bundles
/preview asset art/slime-v1       Open a specific revision (spaces are supported)
/preview status                  Show tracked game state and recent diagnostics
/preview stop                    Stop only the game Daydream launched
```

No model request is needed. The command also appears as **Preview game or asset**
in the command palette, while a session is open. Restart OpenCode if the new TUI
part has not been discovered; no extra install flag is needed. Agent-only
installations do not include it.

Use `/assets [bundle]` to manage candidates, approve artwork, request changes,
or add/update an asset. `/preview` has no approval submenu or decision alias;
`/preview asset` remains read-only. OpenCode's built-in `/review` is code review.
See [Your assets](REVIEW.md).

## Game preview

Daydream launches the **entire current project**, using its configured main scene
in `project.godot`, in a normal graphical Godot window. This is not a browser
export, embedded game window, editor remote-control connection, or headless test.

The executable is selected from `.daydream/preview.json`, then `GODOT_BIN`, then
`godot` on the OpenCode server's PATH. For a pinned project, explicitly configure
the matching engine; Daydream does not guess an executable from prose in AGENTS.md:

```json
{
  "godot": "/absolute/path/to/godot",
  "version": "4.7.2"
}
```

This is an example, **not a request to upgrade your game's engine**. Choose your
game's own version. Relative executable paths resolve from the project root.
`version` is optional but, when present, must match the binary's version (a short
`4.x.y` pin also accepts its build suffix). Only Godot 4 is supported. No shell
commands, arbitrary flags, game settings, or project configuration are rewritten.
Custom shell-based run workflows are not interpreted; launch those through the
project's existing documented procedure instead.

The command confirms the launch and honors OpenCode read, `daydream.preview.game`,
and edit permissions **before executing even the version check**. Godot can execute
project scripts/addons/native extensions, contact services, and write `.godot/`,
resource imports and save data. Only preview trusted projects. This is not a
sandbox and the plugin does not widen saved permissions. Permissions resolving
to `allow` need no additional server prompt; the TUI still confirms launch.

One owned game process per project/plugin instance is allowed. Repeating Game
returns the running instance rather than launching another. Status retains the
last 8 KiB of output and exit code; treat those diagnostics as potentially private.
Snapshots omit unknown fields such as `code` and `signal` while running, rather
than returning JavaScript `undefined`, which OpenCode's RPC JSON validation rejects
before serialization. Actual zero exit codes and null codes on signal termination
are preserved. The status dialog displays a numeric exit code or termination signal.
Stop sends TERM, then KILL if necessary, **only to the ChildProcess it owns**.
It never searches process names, adopts PIDs, closes your editor, or kills game
instances you launched yourself. Processes started by game scripts are not managed.
Plugin unload/reload stops owned previews; closing the terminal alone may leave
a game running if the shared server/plugin remains active. A server crash cannot
guarantee cleanup, and a restarted plugin will not adopt old PIDs.

The game window opens on the **server machine's desktop**, usually the same local
machine as the TUI. A remote/headless server cannot stream a game window to your
client; run OpenCode alongside Godot on the desktop where you want to play. There
is no streaming or silent headless fallback. Startup errors are available through
Status. A running process is not proof the game looks correct or has been tested.

## Asset preview

The picker supports static sprites, animations and [environment tilesets](TILESETS.md).
It now uses the shared [asset browser](ASSET_LIFECYCLE.md): current candidates by
default, older revisions on request, imported/manual-edit status and optional
validated thumbnail overview. New automatic revisions are under `.daydream/revisions`;
the configured source root is still scanned for existing candidates.
Tileset viewers include numbered tiles, collision outlines, seam counts and a
placed layout. The picker scans the configured `.daydream/config.json` `paths.sources` directory
(default `art`), bounded to 2,000 directories and 500 revision candidates. Choose
**Enter revision path…** or pass a path for candidates elsewhere in the project.
Candidates are not assumed valid merely because they appear in the list.

On selection, the shared Python sprite/animation inspector validates the exact
revision and artifacts. The viewer embeds hash-checked PNG/APNG data, transparency,
nearest-neighbor rendering, contact sheets, and the revision hash in a self-contained
HTML document. Use the shared **Artwork scale** control for a closer look. Playback follows the generated
APNG loop/timing; there is no frame editor or approval button here.

After confirmation, the TUI opens that document with the system default browser
(`xdg-open` on Linux, `open` on macOS), using an argument list, not a shell. The
server never opens a browser. For remote connections the authorized viewer data
is transferred to the client, rather than treating server paths as local files.

Explicit [collision geometry](COLLISIONS.md) also shows placed-layout coverage,
yellow solid/cyan one-way outlines and exact polygon/settings listings. Raster
overlays approximate half-pixel coordinates; they are not a physics test or alpha tracing.
No local web server, port, account, or remote image URL is used. The document has
a restrictive content-security policy. One fixed, SHA-256-allowlisted script
switches embedded older-version panels, shared pixel scale and motion replay; it performs no
network, filesystem, approval or import actions. All labels, notes and details
are HTML-escaped. Revision paths cannot
traverse outside the active project or pass through symlinks.

After a guided add/update, **Preview this scene** launches the saved standalone
scene with the same game-code permissions and tracked stop/status behavior. It
does not replace `run/main_scene`. A different running preview must be stopped
explicitly before launching the scene; no editor or unrelated game is killed.

### Previous-version comparison

Asset previews from both `/assets` and `/preview asset` use the same renderer.
The shared `assets.list` discovery returns parent revision hashes along with
identity and timestamps. Comparison selects the recorded ancestry first, then
earlier same-kind/same-ID candidates by saved-file time; identical hashes are
deduplicated. It never follows provenance as a filesystem path. An unavailable
recorded parent gets an explicit placeholder, not a silently substituted version.

Every embedded revision is fully inspected and its images rechecked against the
validated manifest before rendering. `review.inspect` supplies exact-revision
feedback snapshots. Current-revision validation failure prevents opening; invalid
history produces an unavailable entry, and denied history discovery produces a
visible notice without retrying. Cancellation discards the viewer. History never
changes the selected hash or the separate review ticket's approval/import target.

Sprite pixels, tile atlases/layouts/collision overlays and APNG motion use a common
native-pixel multiplier. Motion PNGs' baked-in 4× enlargement is normalized before
display. Images scroll rather than independently shrinking to fit, preserving
equal scale even for different sizes. Numbered tile sheets and contact sheets
remain reference details with their own layouts. Animation clips run independently,
not as a synchronized frame-by-frame comparison. **Replay motion** restarts the
visible clips using local PNG blobs made from the embedded bytes, including when
the reference picker changes; replaced blob URLs are revoked. Narrow screens stack panels.

**Loop preview** is enabled by default and repeats only visible non-looping,
multi-frame clips. `animation.inspect` supplies each preview's saved `loop` flag
and total `duration_ms`, summed from the same rounded/coalesced timing used to
encode its APNG. After an image loads, a timer replays that clip from its cached
local PNG blob at the end of the cycle. Already-looping APNGs retain their native
playback. Turning the checkbox off replays once using saved settings. Timers are
cleared when comparisons change, the page is hidden or it closes; visible playback
resumes when the page returns. This control writes no source/manifest/PNG/import
files and does not grant artwork approval. Browser scheduling may add a small
delay at replay boundaries; this is review playback, not a Godot timing guarantee.

Rendering/validation still requires optional Pillow. Each revision is limited to
10 MiB of raw image data. Comparison embeds up to eight earlier versions with a
14 MiB combined body/feedback budget; oversized references show an unavailable
entry. The client retains its 16 MiB whole-document limit. More history remains
accessible through **Show older revisions**. Up to 20 private temporary viewers per TUI lifetime are retained
for reloads, then deleted on TUI cleanup; a hard crash may leave temporary files.
Only its own temporary directories are removed. Preview does not create project
metadata, approve art, import assets, or change source revisions.

## Architecture and validation

The existing server plugin owns a shared runtime preview service. A documented
OpenCode RPC and native `daydream_preview` tool adapt that same service. The TUI
part supplies the slash command, dialogs and local browser opening. The stateful
process manager is not duplicated in the short-lived Python CLI; `daydream ops`
continues to describe the filesystem asset catalog, not live game processes.

Tests cover permission denial, engine pins, duplicate/concurrent launches, owned
process cleanup, failures/diagnostics, asset validation/tampering, paths, browser
arguments, and slash-command confirmation/cancellation. Native tool loading and
Status execution have been exercised in live OpenCode. The optional graphical
fixture test starts/stops a synthetic project, but does not establish human visual
review, play feel, or end-to-end TUI/browser interaction.

Relevant OpenCode V2 interfaces: [TUI commands/dialogs](https://opencode.ai/v2/docs/build/plugins/cli),
[server permissions/tools](https://opencode.ai/v2/docs/build/plugins/server),
and [typed RPC](https://opencode.ai/v2/docs/build/plugins/rpc).
