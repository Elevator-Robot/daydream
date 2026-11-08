# Daydream

**Dream it. Make it playable.**

Create pixel-art sprites, animations, walls and floors for your Godot game.
Describe what you want, preview the result, request changes, and decide when to
add it to your project. Daydream also helps with game code and debugging.

> **Early access:** the current art workflow focuses on pixel art. General image
> generation and automatic level design are not available. Review the artwork and
> playtest changes in Godot before using them in your game.

## Before you start

- Linux or macOS, with Python 3.9+ and Git.
- [OpenCode V2](https://opencode.ai/v2/docs/), installed and connected to a model.
- Godot 4 matching your game. Tile layouts require Godot 4.3 or newer.
- Access to this repository.

## Install

Clone Daydream into a permanent location:

```sh
git clone https://github.com/Elevator-Robot/daydream.git ~/Code/daydream
cd ~/Code/daydream
```

Preview the installation, then apply it when you're ready:

```sh
python3 scripts/install.py
python3 scripts/install.py --apply
```

Keep this folder in place after installing. Existing conflicting files will not
be replaced. Restart OpenCode after installation.

### Enable pixel-art creation

Run these commands once from the Daydream folder:

```sh
python3 -m venv .venv-sprites
.venv-sprites/bin/python -m pip install -r requirements-sprites.txt
```

This installs the image support in Daydream's own Python environment. You can skip
it if you only want help with game code.

## Open your game

```sh
daydream /path/to/your/game
```

Or run `daydream` from inside the game folder. Each launch opens a fresh session;
use OpenCode's session picker to return to an earlier conversation.

For your first experiment, use a separate test project or scene. Keep your game
under version control and save any unsaved Godot work before requesting file changes.

## Make your first asset

Ask in chat, or open **`/assets` → Describe a new asset…**:

> Create a transparent 32×32 slime named Moonlight Slime. Use a soft purple palette
> and show me a candidate before adding it to the game.

Then:

1. Open **`/assets`** and select the candidate.
2. Inspect its browser preview. For animation, watch it move.
3. Choose **Request changes** or **Approve artwork**.
4. If asked for a **reviewer label**, enter your name or simply **`user`**.
5. Choose **Add or update in project**. **Add a separate copy** is the safe choice
   for your first test; filenames are handled for you.
6. Read the summary, then separately confirm adding the asset.
7. Choose **How to open it in Godot** or **Preview this scene**.

**Approval does not add the asset yet. Adding a separate copy does not place it
into your existing level.** Ask for that integration when you are ready.

Use friendly names with spaces and capitals. Daydream keeps versions for you;
you don't need to invent filenames or `v1/v2` suffixes.

Full walkthrough: **[Your assets](docs/REVIEW.md)**.

## Three commands to remember

| Command | Use it for |
| --- | --- |
| `/assets` | Create, browse, preview, approve and add/update artwork |
| `/preview game` | Playtest the project's normal starting scene |
| `/preview stop` | Stop the game preview Daydream started |

Use `/preview status` when a game preview fails. `/preview asset` is available if
you only want to view artwork. OpenCode's `/review` is for **code review**, not art.

## What would you like to make?

- **[Sprites and animations](docs/SPRITE_WORKFLOW.md)** — characters, props, idle
  animations and movement frames.
- **[Walls, floors and terrain](docs/TILESETS.md)** — matching tiles, edges and corners.
- **[Ramps and platforms](docs/COLLISIONS.md)** — blocking shapes and one-way platforms.
- **[Editable layouts in Godot](docs/EDITOR_LAYOUTS.md)** — paint generated layouts
  before playing.
- **[Versions and updates](docs/ASSET_LIFECYCLE.md)** — keep history and protect manual edits.
- **[Preview and playtest](docs/PREVIEW.md)** — run the game or inspect a standalone scene.

For coding help, try:

> Explain how this game is organized and suggest one small improvement. Don't
> change anything yet.

> Add a double jump using the existing player movement code. Keep the controls
> and tell me how to test it.

## Update Daydream

From the folder where you cloned Daydream:

```sh
git pull --ff-only
python3 scripts/install.py
python3 scripts/install.py --apply
```

Restart OpenCode afterwards. If Git reports local changes or the installer reports
a conflict, resolve those before continuing—don't discard your files.

## Need help?

Run `daydream --doctor` for a setup check, or see **[Troubleshooting](docs/TROUBLESHOOTING.md)**.
Use `daydream --no-intro` to start without the optional opening animation.

Already using OpenCode and only want the coding agent? Install with
`python3 scripts/install.py --agent-only --apply`. That lighter option does not
include `/assets`, previews or the launcher.

---

Contributing to Daydream? See the [development guide](docs/DEVELOPMENT.md).
