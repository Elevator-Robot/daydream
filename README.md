# Daydream

**Dream it. Make it playable.**

Your AI coding and pixel-art companion for Godot. Open a project, describe what
you want to change, and work with Daydream on scripts, scenes, sprites, and debugging.

> **Early access:** Daydream supports coding, pixel-art sprites, and a first
> frame-based animation workflow. General AI image generation and automatic game
> assembly are not available yet. Review artwork and motion, then playtest in Godot.

## Before you start

- **Linux or macOS** with **Python 3.9+** and **Git**.
- **[OpenCode V2](https://opencode.ai/v2/docs/)**, installed and connected to a model.
- **Godot 4**, matching your game's version, when you want to run project checks.
- Access to this repository.

The animated intro is optional. Daydream works without `ttfx` installed.

## Install

Clone Daydream into a permanent location:

```sh
git clone https://github.com/Elevator-Robot/daydream.git ~/Code/daydream
cd ~/Code/daydream
```

Preview the installation:

```sh
python3 scripts/install.py
```

Review the preview, then install:

```sh
python3 scripts/install.py --apply
```

Keep the cloned folder in place after installing. The installer refuses to
replace conflicting files and does not change your model settings or permissions.

## Start Daydream

Open your game's directory and run:

```sh
cd /path/to/your/game
daydream
```

Or choose a directory directly:

```sh
daydream /path/to/your/game
```

Daydream opens ready for your first request—no greeting message needed to start
it. Each launch creates a new session without editing your project. Use the
session picker to return to an earlier conversation.

### Try your first request

Start by getting familiar with the project:

> Explain how this game is organized, identify the main scene, and suggest one
> small improvement. Don't change anything yet.

Then ask for a specific change:

> Add a double jump to the player using the existing movement code. Keep the
> current controls and explain how to test it.

Or investigate a problem:

> The player sometimes falls through this platform. Find the cause and propose
> the smallest fix before making changes.

Give Daydream the scene, behavior, and expected result when possible. Use version
control, review its changes, and playtest the result in Godot. Only open projects
you trust.

## Preview your game or artwork

In an OpenCode session, run `/preview` to choose **Game** or **Asset**.
Use `/preview game` to launch the whole project's main scene in graphical Godot,
`/preview asset` to browse sprite/animation candidates, and `/preview stop` to
stop the game Daydream launched. `/preview status` shows game diagnostics.

Game preview executes project code and asks for authorization. The standard
install includes the command; it does not need a model call. See
[preview setup and engine pins](docs/PREVIEW.md).

## Pixel-art sprites (optional)

The standard install includes the [native tools interface](docs/OPERATIONS.md)
for discoverable sprite and animation actions. Existing users can rerun the
standard installer to add missing components without replacing matching links.
Pillow remains a separate optional dependency for rendering.

Enable sprite creation and editing once from your Daydream checkout:

```sh
cd ~/Code/daydream
python3 -m venv .venv-sprites
.venv-sprites/bin/python -m pip install -r requirements-sprites.txt
```

Then open your game with `daydream` and try:

> Create a transparent 32×32 slime using five colors. Show me the preview before
> adding anything to the game.

> Make the outline darker and keep the original version.

Review the preview before approving it. Daydream can then add the approved sprite
as a static Godot scene, without replacing existing assets. This first workflow
uses explicit pixel designs, not a paid image-generation service.

For animation, try:

> Give the slime a four-frame idle animation. Keep its feet aligned and show me
> a motion preview before importing it.

Daydream can build ordered frames with timing and looping, then import an
approved animation as a Godot scene. Watch the motion preview before approving;
a still image alone cannot show whether it moves correctly.

Follow the [sprite workflow](docs/SPRITE_WORKFLOW.md) from the first brief through
revisions, approval, import, and testing in Godot.

For walls and floors, Daydream can generate matching terrain transitions from
your pixel-art seed tiles, check their seams, preview a layout, and import an
approved Godot TileSet with collision flags. See the [environment-art workflow](docs/TILESETS.md).

## Useful options

```sh
daydream --no-intro  # start without the animation
daydream --doctor    # check your setup without opening a new session
daydream --help      # show available options
```

Already using OpenCode and only want the Daydream agent?

```sh
python3 scripts/install.py --agent-only         # preview
python3 scripts/install.py --agent-only --apply
```

Restart OpenCode, then select `daydream` from its agent selector.

## Troubleshooting

**`daydream: command not found`**

Make sure installation completed, then add the command directory to your current
terminal's PATH:

```sh
export PATH="$HOME/.local/bin:$PATH"
daydream --doctor
```

Add that PATH entry to your shell's startup configuration if it is missing in
new terminals too.

**Daydream won't start**

Run `daydream --doctor`. Make sure OpenCode V2 is installed, then review the
installer preview and rerun it with `--apply` if something is missing. If it
reports a conflicting file, inspect it rather than overwriting it.

**The intro doesn't appear**

The animation needs `ttfx`; it is not required to use Daydream. Use
`daydream --no-intro` to start without it.

## Update

From the folder where you cloned Daydream:

```sh
git pull --ff-only
python3 scripts/install.py
python3 scripts/install.py --apply
```

Start a new Daydream session to use the update. If Git reports local changes or
an installer conflict, resolve those before continuing—don't discard your files.

---

Contributing? See the [development guide](docs/DEVELOPMENT.md).
