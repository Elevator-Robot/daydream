# Preview games and assets

The standard Daydream plugin includes a native OpenCode TUI command:

```text
/preview                         Choose Game, Asset, Status, or Stop
/preview game                    Run the configured main scene in Godot
/preview asset                   Browse sprite/animation/tileset revision bundles
/preview asset art/slime-v1       Open a specific revision (spaces are supported)
/preview status                  Show tracked game state and recent diagnostics
/preview stop                    Stop only the game Daydream launched
/preview review                  Review/approve an exact asset revision
```

No model request is needed. The command also appears as **Preview game or asset**
in the command palette, while a session is open. Restart OpenCode if the new TUI
part has not been discovered; no extra install flag is needed. Agent-only
installations do not include it.

The picker also offers **Review / approve asset**. `/asset-review [bundle]` opens
the same review flow directly, with explicit approval/change requests and a
separate import plan/apply step. `/preview asset` remains read-only. OpenCode's
built-in `/review` code-review command is not replaced. See [review](REVIEW.md).

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
Tileset viewers include numbered tiles, collision outlines, seam counts and a
placed layout. The picker scans the configured `.daydream/config.json` `paths.sources` directory
(default `art`), bounded to 1,000 directories and 100 revision candidates. Choose
**Enter revision path…** or pass a path for candidates elsewhere in the project.
Candidates are not assumed valid merely because they appear in the list.

On selection, the shared Python sprite/animation inspector validates the exact
revision and artifacts. The viewer embeds hash-checked PNG/APNG data, transparency,
nearest-neighbor rendering, contact sheets, and the revision hash in a self-contained
HTML document. Use browser zoom for a closer look. Playback follows the generated
APNG loop/timing; there is no frame editor or approval button here.

After confirmation, the TUI opens that document with the system default browser
(`xdg-open` on Linux, `open` on macOS), using an argument list, not a shell. The
server never opens a browser. For remote connections the authorized viewer data
is transferred to the client, rather than treating server paths as local files.

Explicit [collision geometry](COLLISIONS.md) also shows placed-layout coverage,
yellow solid/cyan one-way outlines and exact polygon/settings listings. Raster
overlays approximate half-pixel coordinates; they are not a physics test or alpha tracing.
No local web server, port, account, or remote image URL is used. The document has
a restrictive content-security policy and no scripts. Revision paths cannot
traverse outside the active project or pass through symlinks.

Rendering/validation still requires optional Pillow. The viewer limit is 10 MiB
of image data. Up to 20 private temporary viewers per TUI lifetime are retained
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
