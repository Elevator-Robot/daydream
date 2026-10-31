# Daydream

**Dream it. Make it playable.**

Daydream is an AI-powered game creation toolkit for Godot, built around OpenCode.
The vision is to create sprites, effects, and assets, then assemble them into
playable Godot scenes. Today, it provides a small, reusable **Godot development
agent for OpenCode** and local validation tools. Keep the expertise here, your
global wiring in dotfiles, and each game's rules in that game's `AGENTS.md`.

This is a starter, not a replacement game editor or an autonomous game studio.
The first target is a dependable loop: **inspect → make one scoped change → run
checks → inspect the real game → iterate → human play-feel review**.

## What exists today

| Included | Not implemented |
| --- | --- |
| Global, project-agnostic Godot agent instructions | Godot editor-control or MCP integration |
| Preview-first, non-overwriting symlink installer | Screenshot capture or automated gameplay input |
| Bounded Godot 4 import / optional headless smoke helper | Asset generation, import pipelines, or model-specific setup |
| Standard-library tests and an isolated Godot fixture | A proven end-to-end loop on your game or desktop |
| Preview-first `.daydream/` configuration generator | Asset provenance recording or approval enforcement |
| Optional in-TUI `ttfx laseretch` intro (entry verified in a real TUI; human visual review pending) | Automatic visual validation of generated assets |

Optional OpenCode plugin hooks are also planned for validation, previews, and
workflow summaries, after explicit tools are proven. No hooks are installed or
implemented today; see the [feature and hook plan](docs/FEATURES.md).

The scripts require **Python 3.9+ on Linux/macOS**. Using the agent requires an
existing OpenCode installation; checking a game requires its compatible Godot 4
**editor** binary. Nothing here downloads software or configures model providers.

## Install only when ready

Clone this repository to a permanent location, then review and preview:

```sh
git clone git@github.com:Elevator-Robot/daydream.git
cd daydream
python3 scripts/install.py
```

The preview makes no changes. To opt in:

```sh
python3 scripts/install.py --apply
```

This creates exactly one symlink:
`~/.config/opencode/agents/daydream.md` → this checkout's `agents/daydream.md`.
It refuses existing files, directories, and other symlinks, including dangling
links; it leaves `opencode.json`, model settings, permissions, and game repos alone.
Re-running it for the same link is harmless. Keep the checkout in place: reviewed
updates to its agent file are reflected through the link.

For the optional **laser-etched Daydream intro**, preview with
`python3 scripts/install.py --with-intro`, then add `--apply` to link both the
agent and the OpenCode V2 TUI plugin. The default install remains agent-only.
The animated intro uses an existing `ttfx` executable—the same effects engine as
Omarchy's screensaver—without installing it or altering desktop settings.
See [intro behavior, reduced motion, and verification](docs/INTRO.md).

With the plugin enabled, choose **Open Daydream** from OpenCode's command palette
to enter an empty Daydream session and play the intro immediately—no first
message needed. The client-side `/daydream` action does the same thing.
The art is explicit-only: normal `/agent` selection, `@daydream` invocation,
session restoration, and ordinary messages do not display it. Use
`/daydream-intro` only when you want to replay it.

For a nonstandard OpenCode config location, explicitly pass
`--config-dir /absolute/config/path` to both preview and apply. This installer does
not infer environment overrides. Check `opencode debug paths` and any
`OPENCODE_CONFIG_DIR` setting first. To uninstall, inspect the installed symlink
and remove **only that link**, not the checkout or the surrounding config directory.

Restart OpenCode, run `opencode agent list`, and look for `daydream`. Inside a game
repository, select it as a primary agent or invoke `@daydream`. `mode: all` supports
both. The definition deliberately sets no model or permission overrides; review
your effective OpenCode permissions before use. Instructions are not a sandbox.
Check for an existing agent named `daydream` in project or JSON configuration if the
loaded behavior differs. [OpenCode agent documentation](https://opencode.ai/docs/agents/)

### Upgrading from the previous name

The agent file and invocation are now `daydream.md` and `@daydream`. The installer
does not migrate existing installations or modify old links. If you previously
installed this project, inspect the old agent symlink and remove only that link
after confirming it belongs to this checkout, then preview and apply the new
installation. Moving the checkout also requires updating any links to its old
location. No global configuration is changed by the rename itself.

Start with a read-only request such as:

> Inspect this project and its AGENTS.md. Identify the expected Godot version,
> main scene, available checks, and one small improvement. Do not edit or run the
> game yet.

Then authorize a particular change and its validation. A game-specific checklist
is in [docs/project-AGENTS.example.md](docs/project-AGENTS.example.md); merge useful
parts into an existing file rather than overwriting it. The repository root's
`AGENTS.md` is for developing **this tool**, not for installing into a game.

## Project-local configuration

For authorized write tasks, the agent is instructed to initialize missing
`.daydream/` metadata without redundant confirmation. Read-only requests never
create files, and project rules and OpenCode permissions still apply.

```sh
python3 scripts/init_project.py /absolute/path/to/game          # preview only
python3 scripts/init_project.py /absolute/path/to/game --apply  # create missing files
```

This creates versioned `config.json`, an empty `assets.json`, `.gitignore`, and
`.gdignore` inside `.daydream/`. Existing files are validated and preserved;
no assets are generated and no engine is launched. See
[configuration, consent, and recovery](docs/PROJECT_CONFIG.md).

## Check a trusted game

First inspect project startup code/addons and match the binary to the game's
engine pin. Importing may execute tool scripts/plugins and write `.godot/` or
resource metadata. It is **not read-only or sandboxed**, even in headless mode.

```sh
# Import only. Replace the executable and project path with your actual paths.
python3 scripts/check_project.py /absolute/path/to/game --godot /path/to/godot

# Also start the configured main scene for up to 60 engine iterations.
python3 scripts/check_project.py /absolute/path/to/game \
  --godot /path/to/godot --smoke-frames 60 --timeout 120
```

The helper checks the binary's reported major version and required CLI flags,
then runs import and, optionally, the main scene. `--timeout` is a wall-clock
limit **per process**; `--smoke-frames` is not a duration in seconds. It fails on
nonzero exit codes, timeouts, or recognized Godot error lines even with exit zero.
It prints command output for review; warnings are not automatically failures.
It does not enforce a project's exact version pin, detect every diagnostic,
exercise every scene/script, build C#, or contain child processes started by game
code. Run only trusted projects and use their established tests too.

No images or input events are produced. Visual changes still need a graphical
run, real evidence from whatever capture tools are available, and human review.
[Godot CLI reference](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)

## Tests

```sh
# No dependencies, engine, network, or user-config writes.
python3 -m unittest discover -s tests -v

# Opt into real-engine happy-path and broken-script tests, in temporary copies.
GODOT_BIN=/absolute/path/to/godot python3 -m unittest discover -s tests -v
```

CI runs the first command only. It does not download Godot or exercise OpenCode.
The fixture is a minimal synthetic project, not a sample game. The real-engine
tests were checked with Godot **4.6.3** in a cloud environment; this is test evidence,
not a request to upgrade a game. OpenCode discovery and a real game/desktop loop
still need verification on the intended machine.

## Next milestone

Prove one authorized change end-to-end in a real game before adding integrations.
See [the roadmap and acceptance criteria](docs/ROADMAP.md) and the proposed
[features and enabling tools](docs/FEATURES.md). No license has been
selected; this private starter does not grant an open-source license.
