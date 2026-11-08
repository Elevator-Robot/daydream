# The `daydream` terminal entry point

Contributor/integration reference. For installation and normal use, see [getting started](../README.md).

The launcher opens the normal OpenCode V2 TUI with a fresh, empty primary
Daydream session. It reuses the existing agent and intro plugin, not another
agent implementation or an external animation window.

## Install

From a permanent Daydream checkout:

```sh
python3 scripts/install.py          # preview the default full setup; no writes
python3 scripts/install.py --apply  # explicitly install
```

This requests four non-overwriting symlinks:

| Destination | Source in the checkout |
| --- | --- |
| `~/.config/opencode/agents/daydream.md` | `agents/daydream.md` |
| `~/.config/opencode/plugins/daydream-intro` | `plugins/daydream-intro/` |
| `~/.config/opencode/plugins/daydream-tools` | `plugins/daydream-tools/` |
| `~/.local/bin/daydream` | `bin/daydream` |

The full setup is the default. `--agent-only` requests only the agent;
`--with-intro` requests the agent, native tools, and intro without a launcher.
`--with-launcher` remains a compatibility alias for the full default. These modes
are mutually exclusive and never remove already-installed components.
Animation's `ttfx` dependency remains optional and is never downloaded.
Matching links are
harmless; conflicting files, directories, or dangling links are refused before
any requested links are created. No shell configuration, provider settings,
permissions, or other repository is edited.

For alternate destinations use `--config-dir /your/opencode/config` and
`--bin-dir /your/bin`. The installer does not guess a config override; check
`opencode debug paths config` first. The bin directory must be on PATH, or use
the command's full path. Keep the checkout in place: the launcher resolves its
own symlink to find its Python helper.

An I/O error or concurrent destination change may leave a partial installation.
Inspect it and rerun after resolving the conflict. Existing user files are never
overwritten or rolled back.

## Open a workspace

```sh
daydream                       # current directory
daydream /absolute/path/to/game # another existing directory
daydream "../game with spaces"  # relative paths work
daydream --no-intro             # no animation; intro/ttfx not required
daydream --doctor               # checks only; no new session
```

Every normal invocation creates a **new session**. Use OpenCode's normal session
picker to return to an old one. A directory without `project.godot` can be opened
for planning; the launcher does not create a game or search other directories.

## What happens

1. Resolve the directory and require an interactive terminal.
2. Find OpenCode on PATH and require V2.
3. Run bounded agent discovery in the target directory. Up to three reads handle
   OpenCode 2.0.32's cold-registry initialization race. Require a visible,
   primary-capable `daydream` agent; never fall back to Build. Only discovery is
   retried; session creation is not.
4. Check for the intro plugin in OpenCode's discovered config directory and an
   existing `ttfx`. If either is absent, warn and open without animation. Install
   nothing automatically. `--no-intro` skips these optional checks.
5. Use `opencode api post /api/session` to create an empty primary Daydream
   session in the explicit directory, through OpenCode's normal authentication.
6. Replace the launcher process with `opencode --session <id> <directory>`.

There is no fake prompt, automatic message, model generation request, engine
launch, game-file write, or `.daydream/` initialization. Project metadata remains
the agent's responsibility within an authorized write task.

No model, provider, permission, or default-agent override is set. OpenCode's
configured defaults remain authoritative; a choice stored only on another
session is not copied or changed. The launcher starts no local model.

OpenCode's existing managed service may start during discovery/session creation.
No extra daemon or endpoint is introduced. The initial launcher targets normal
service discovery: it does not add a separate `--standalone` server or construct
unauthenticated HTTP requests. It does not forward arbitrary OpenCode flags such
as `--auto`, `--prompt`, or model overrides.

If launch fails after creation, an empty session may remain; the error identifies
it when available. The launcher does not automatically delete sessions, repeat
creation, or retry a model request.

## Immediate, explicit intro

The launcher passes the new session ID in client-local
`DAYDREAM_LAUNCH_SESSION`. The plugin consumes and clears this marker, waits for
the matching primary session, and requests its intro once. Ephemeral plugin
memory prevents replay on remount/hot reload; no persistent startup flag is saved.

Only the explicit terminal entry, **Open Daydream**, and `/daydream-intro` request
art. Ordinary `/agent` selection, mentions, session restoration, and messages
still do not. See [intro behavior](INTRO.md) for reduced motion and appearance.

Disabled plugins or nonstandard manually configured plugin locations can prevent
animation. `--doctor` checks discoverable files, not graphical appearance. The
agent remains usable without it.

## Dependencies and diagnosis

- Python **3.9+**, **OpenCode V2**, and an installed Daydream agent.
- Optional `ttfx` and the intro plugin for animation. No Godot binary is needed
  merely to open the assistant.
- `--doctor` works without a TTY and creates no session, prompt, or game files.
  OpenCode may still perform its normal service/configuration/cache initialization.
- Tests use fake OpenCode executables and temporary config/bin directories, never
  actual user configuration or another game repository to test installation.

To uninstall, inspect and remove only the launcher symlink. Keep the agent and
intro links if desired. Never remove a later replacement command, the whole bin
directory, or the source checkout blindly.

## Validation

The isolated unit suite covers missing dependencies, cold discovery, failed API
calls, malformed responses, paths with spaces, symlink launching, noninteractive
use, cancellation, and collision refusal. A real OpenCode 2.0.32 pseudo-terminal
run from outside this checkout also verified a fresh workspace: one primary
Daydream session, zero messages, immediate owned `ttfx` playback, unchanged game
files, and no `.daydream/` initialization. This proves startup behavior, not a
sprite workflow, Godot editor control, or human visual correctness.
