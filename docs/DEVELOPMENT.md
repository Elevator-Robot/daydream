# Developing Daydream

The root [README](../README.md) is the end-user installation and usage guide.
This document contains contributor checks and technical validation boundaries.
Read the repository's `AGENTS.md` and [roadmap](ROADMAP.md) before changing scope.
The installable instructions are `agents/daydream.md`; the root contributor
instructions must never be installed as a game's global instructions.

## Tests

```sh
# No engine, network, or actual user-config writes.
python3 -m unittest discover -s tests -v

# Opt into real-engine checks in temporary fixture copies.
GODOT_BIN=/absolute/path/to/godot python3 -m unittest discover -s tests -v

# Also exercise the installed text-effects engine, if available.
TTFX_BIN=/absolute/path/to/ttfx GODOT_BIN=/absolute/path/to/godot \
  python3 -m unittest discover -s tests -v
```

Python helpers use the standard library. Node.js is optional for the Python
suite; when present it runs the intro's dependency-free JavaScript tests and
syntax check. Without Node, those checks are skipped. CI runs the ordinary unit
suite and does not download Godot or exercise an OpenCode UI.

The suite also runs the native adapter, preview and user-review Node tests. With
Pillow enabled, review tests use the real Python backend in disposable projects
for all asset kinds. See [review validation](validation/2026-11-05-asset-review.md)
for the separate actual OpenCode TUI test; unit tests alone do not establish UI
interaction or human artwork approval.

The real-engine tests import and briefly run an isolated synthetic fixture and
verify a broken-script case. The fixture is not a sample game. Initial cloud
validation used Godot 4.6.3; subsequent local checks used 4.7.2. Neither is a
request to upgrade a game's engine pin.

## Check a trusted Godot project

### Optional sprite workflow checks

Pillow is intentionally separate from the core dependency-free helpers:

```sh
python3 -m venv .venv-sprites
.venv-sprites/bin/python -m pip install -r requirements-sprites.txt
GODOT_BIN=/absolute/path/to/godot .venv-sprites/bin/python -m unittest discover -s tests -v
```

Sprite tests are skipped without Pillow; schema validation still runs. Real
resource checks use temporary Godot fixtures, not another game repository.
See [the sprite slice](SPRITES.md) for source/edit formats, approval boundaries,
import recovery, and the remaining human/graphical acceptance criteria.

The preview command's optional **graphical** process check runs only an isolated
synthetic scene and stops its owned Godot child (a desktop/display is required):

```sh
DAYDREAM_GRAPHICAL_TEST=1 GODOT_BIN=/absolute/path/to/godot \
  DAYDREAM_TEST_PYTHON=/path/to/sprite-venv/bin/python node --test tests/preview.test.mjs
```

This verifies process launch/stop, not that a human watched the game window or
browser playback. No actual user project or configuration is used.

### Project import/smoke helper

Inspect startup code, tool scripts, addons, native extensions, and external
services before import. Importing can execute code and write `.godot/` or resource
metadata. Headless execution is not read-only or sandboxed.

```sh
# Import only; replace both paths with the project's actual paths.
python3 scripts/check_project.py /absolute/path/to/game --godot /path/to/godot

# Also run the configured main scene for up to 60 engine iterations.
python3 scripts/check_project.py /absolute/path/to/game \
  --godot /path/to/godot --smoke-frames 60 --timeout 120
```

The helper checks the binary's reported major version and required flags, then
runs import and an optional smoke check. `--timeout` is a per-process wall-clock
limit. `--smoke-frames` counts engine iterations, not seconds. Nonzero exits,
timeouts, and recognized Godot error lines fail; warnings are printed for review.

It does not enforce the exact project pin, detect every diagnostic, exercise all
scenes/scripts, build C#, or contain child processes started by game code. Use the
game's existing checks too. No screenshot or input evidence is produced. Visual
changes need a graphical run, real capture evidence when available, and human
play-feel review. Never infer appearance or usability from headless success.

## Installation and project boundaries

- Keep installation preview-first, opt-in, and non-overwriting. Use temporary
  config/bin destinations for installer tests, never actual user configuration.
- Keep engine pins, paths, design decisions, assets, and test commands in the
  game's own `AGENTS.md`. See [the example project checklist](project-AGENTS.example.md).
- When migrating an older installation or moving the checkout, inspect existing
  symlinks first. Remove only confirmed obsolete links; never overwrite unrelated
  configuration or an existing game's instructions.
- Launcher integration has been exercised in a real OpenCode 2.0.32 TUI using a
  fresh temporary workspace: primary Daydream session, zero messages, immediate
  intro, unchanged game files, and no project-local metadata writes. This is not
  proof of the full game-development or asset-generation workflow.
- No project license has been selected. Repository access does not grant an
  open-source license; do not add one on the owner's behalf.

## Further documentation

- [Launcher](LAUNCHER.md): installation modes, startup, dependencies, and consent.
- [Intro](INTRO.md): playback, reduced motion, and visual verification.
- [Project configuration](PROJECT_CONFIG.md): local initialization and recovery.
- [Static sprites](SPRITES.md): create/edit/approve/import workflow and limits.
- [Frame animation](ANIMATIONS.md): timing, motion previews, approval, and Godot resources.
- [Operations](OPERATIONS.md): shared catalog, CLI, native adapter and validation boundaries.
- [Preview](PREVIEW.md): user slash command, owned Godot runtime and browser asset viewer.
- [Environment tiles](TILESETS.md): shared tile generation, seams, terrain, layout and collision checks.
- [Review and approval](REVIEW.md): user-only decisions, retained feedback and exact-plan import.
- [Tile collisions](COLLISIONS.md): convex geometry, presets, overlay review, compatibility and physics fixtures.
- [Feature plan](FEATURES.md): proposed creative tools and hook safeguards.
- [Roadmap](ROADMAP.md): implemented capabilities and acceptance criteria.

Use the official [OpenCode V2 documentation](https://opencode.ai/v2/docs/) and
[version-matched Godot documentation](https://docs.godotengine.org/) for interface
changes. Do not introduce a service or broaden permissions without a concrete
requirement and a separately reviewed design.
