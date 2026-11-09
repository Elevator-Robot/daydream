# Working on Daydream

Daydream is being built as a **Summer Engine alternative for stock Godot and
OpenCode**: an idea-to-playable product that creates/revises sprites, animations,
effects and other assets, assembles them into games, and helps verify the result.
It is not merely a prompt collection or a folder of shell helpers. This repository
is the reusable product, not a game project. Current capabilities are a subset of
that goal; do not imply complete Summer parity or implemented editor control.

## Product and architecture direction

- Keep the Summer Engine alternative goal central when prioritizing work. Measure
  success by coherent user workflows and usable Godot results, not the number of
  helper scripts or passing isolated tests.
- Study Summer's public CLI/agent/tool source and documented behavior for proven
  strategies. Pin research to source revisions, distinguish code evidence from
  marketing claims, and record findings in `docs/research/`. Do not install or run
  Summer, contact paid services, access closed editor code, or copy source/assets
  without separate authorization and appropriate license review.
- Prefer one reusable capability implementation with typed, discoverable operations,
  shared input validation, structured results/errors, and CLI/native OpenCode tool
  adapters. Do not make the model rediscover implementation files or reassemble
  shell commands for every normal product action.
- Expose common workflow actions as native tools; retain a discoverable operation
  catalog and CLI for advanced/fallback use. Internal Python modules are libraries,
  not independent model-facing tools. Avoid duplicated CLI/plugin business logic.
- Prefer documented native OpenCode V2 integration for this product. Summer's use
  of MCP does not itself justify adding an MCP server, daemon, remote endpoint,
  account system, cloud dependency, telemetry, or permission auto-approval here.
- Keep preview-before-apply, exact-revision approval, non-overwriting writes,
  cancellation, and honest evidence in the shared implementation, not only prompts
  or adapters. Tools must not auto-approve artwork or hide failed/partial outcomes.
- Normal asset workflows use friendly labels and automatic hidden revision paths.
  Keep raw IDs/paths/hashes as details, not required user knowledge. Explicit
  managed updates may replace only verified unchanged registered outputs after
  exact-plan confirmation and a complete recovery snapshot; new imports stay
  non-overwriting. Never migrate/delete an existing game's history automatically.
- Prefer extending shared sprite/animation capabilities over one-off per-game
  generators when addressing a recurring product gap. Preserve existing game work;
  do not rewrite another repository as an architectural cleanup.

## Guided user experience

- Use natural, direct language in user-facing text. Avoid formulaic assistant
  phrasing and decorative punctuation, especially frequent em dashes. Prefer short
  sentences, commas or colons where they read naturally.
- Keep viewing modes predictable. On desktop, single-image information sits neatly
  to the right; comparison places information below each image. Use a subtle
  transition, preserve selected asset context and respect reduced-motion settings.
  Narrow layouts keep information below the image. Keep labels and controls consistent.

- Treat an intuitive, guided workflow as a standing product requirement. Show the
  current step and a concrete next action; do not leave users to infer how to proceed.
- List instructions and menu actions in order of operation, with prerequisites
  before dependent actions. For assets, use: describe → review/revise → approve →
  add/update → preview. Revisions return to review rather than skipping ahead.
- Put relevant next actions ahead of history, help and advanced details. Keep Back,
  Finish and Cancel easy to find. Highlighting a next step must never execute it.
- Carry the selected asset and project through the flow. Avoid asking users to
  remember names, paths, hashes or instructions already available to Daydream.
- Use consistent, task-oriented labels across dialogs, previews, agent responses
  and documentation. Explain what a step accomplished and what remains, especially
  the difference between a candidate, approval, added resource files and gameplay placement.
- Prefer short numbered procedures and progressive detail over long explanations
  or extra confirmation screens. Preserve exact-review and separate-apply boundaries.

## Contributor boundaries

- Read `README.md` and `docs/ROADMAP.md` before changing the scope.
- User documentation teaches tasks, menu choices and expected results. Keep
  schemas, RPC/adapter details, internal storage algorithms and test evidence in
  contributor/reference/validation docs. Start users at `docs/README.md`; link
  implementation readers through `docs/DEVELOPMENT.md` and `docs/reference/`.
- `agents/daydream.md` is the installable agent. This file is only for contributors
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
  is available, also run the isolated fixture check in `docs/DEVELOPMENT.md`.
- Preserve user edits. Do not publish, merge, install software, or broaden
  permissions beyond the current request. Do not add secrets or choose a license
  on the owner's behalf.
