# Working on godot-agent

This repository builds reusable Godot development instructions and small, local
tools for OpenCode. It is not a game project.

- Read `README.md` and `docs/ROADMAP.md` before changing the scope.
- `agents/godot.md` is the installable agent. This file is only for contributors
  working on this repository; never install it as global game instructions.
- Keep game-specific paths, engine pins, design decisions, and test commands in
  the game's own `AGENTS.md`, not in the global agent.
- Prefer Python's standard library and documented Godot/OpenCode interfaces.
  Do not introduce an MCP server, daemon, network service, or asset pipeline
  without a concrete requirement and a separately reviewed design.
- Keep installation opt-in, previewable, and non-overwriting. Never modify a
  user's actual config or another repository to test installation.
- Keep implemented capabilities distinct from planned ones. Headless checks do
  not establish graphical correctness, editor interaction, or play feel.
- Run `python3 -m unittest discover -s tests -v` after changes. If a Godot 4 editor
  is available, also run the isolated fixture check documented in the README.
- Preserve user edits. Do not publish, merge, install software, or broaden
  permissions beyond the current request. Do not add secrets or choose a license
  on the owner's behalf.
