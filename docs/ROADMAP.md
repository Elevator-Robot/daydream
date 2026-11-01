# Daydream — scope and next milestones

Internal milestones and acceptance criteria. For installation and everyday use,
see the [user README](../README.md).

## Vision

**Dream it. Make it playable.** Daydream aims to create sprites, effects, and
assets, then assemble them into playable Godot scenes. This is the product
direction, not a claim that generation or automated assembly works today.

See [features and enabling tools](FEATURES.md) for the proposed creative feature
set, candidate tools, and a first asset-creation milestone.

## Boundaries

- **Daydream:** reusable instructions, narrow helpers, tests, installation docs.
- **dotfiles:** optional global wiring only, added separately when authorized.
- **each game:** engine pin, controls, architecture, design intent, assets, tests,
  and its own `AGENTS.md`. A test game is not a global dependency.

The initial implementation is intentionally filesystem/CLI-based. No background
service, Godot addon, MCP endpoint, screenshot mechanism, or remote-control port
is installed. Existing OpenCode configuration remains the authority for tools
and permissions. Future integrations need their own permission/trust review.

## 0 — Starter (implemented)

- Installable Markdown agent with project discovery, scoped edits, validation,
  evidence boundaries, and human review in its workflow.
- Preview-first, non-overwriting installation of launcher, agent, and intro by
  default, with `--agent-only` for lightweight OpenCode integration.
- Optional OpenCode V2 TUI intro, included in the full install, using the installed
  `ttfx laseretch` engine, with bounded playback, reduced motion, and session
  scoping. Its frame decoder is tested against the real engine. This is cosmetic UI, not a
  server workflow hook. Entry without a message was verified in the installed
  TUI via a pseudo-terminal; [human visual review remains pending](INTRO.md).
- An **Open Daydream** client-side menu action opens an empty primary session
  and triggers the intro before any message/model call. It does not change the
  built-in home-screen agent selector, whose selection state is not exposed.
- A [terminal launcher](LAUNCHER.md), `daydream [directory]`, with bounded
  preflight, an empty primary-agent session, immediate client-local intro intent,
  and `--doctor`/`--no-intro`. It changes no model defaults, permissions, or game
  files. Installation is preview-first; `--apply` is still required for writes.
- Preview-first, non-overwriting `.daydream/` initialization with versioned
  config/metadata containers, path validation, and agent consent instructions.
  See [project-local configuration](PROJECT_CONFIG.md). This does not implement
  asset generation, record-level provenance validation, or runtime hooks.
- Godot 4 CLI helper with project validation, supported-flag checks, per-process
  timeout, error-output inspection, and optional main-scene smoke run.
- Dependency-free unit tests, opt-in real-engine tests in temporary fixture
  copies, and a read-only-permissions CI workflow for the unit suite.

This milestone does **not** prove OpenCode loads the agent on the user's machine
or that the agent can complete a game change autonomously.

## 1 — Static sprite workflow (implemented tools; human/real-game acceptance pending)

- Optional Pillow-backed pixel-grid rendering, transparent PNG output, and
  enlarged checkerboard previews. No image-generation API or automatic install.
- Fresh revision bundles for recolor, mirror, paint, and rectangle edits, plus
  bounded conversion of existing palette-limited PNGs.
- Revision/preview hashes, explicit user-review records, and rejection of stale
  approvals or tampered artifacts. Records are not authenticated identity.
- Preview-first, non-overwriting static Godot PNG/source/scene import and
  project-local provenance records. Existing scenes and main-scene settings stay
  untouched; generated `Sprite2D` scenes use nearest filtering.
- Isolated unit tests, actual PNG preview inspection, and a real Godot resource
  import/startup check. See [scope, commands, and remaining review](SPRITES.md).

**Still pending:** user art approval, graphical verification in a real game, and
the broader loop below. Animation, resize, provider generation, and full scene
assembly remain out of scope for this slice.

## 2 — Prove the real game loop (next; not yet done)

On an authorized development machine with a trusted Godot project:

1. Install or manually wire the agent; verify `opencode debug agents` discovers it.
2. Capture a baseline: game commit/working changes, exact engine and OpenCode
   versions, test commands, and a reproducible scene/interaction.
3. Choose one small observable code or approved-static-sprite change with
   acceptance criteria. No redesign, engine migration, or animation pipeline.
4. Let the agent inspect, edit, and run appropriate checks; inspect the diff and
   distinguish pre-existing failures from regressions.
5. Launch the actual game with its normal renderer. Capture and inspect a real
   screenshot using an available tool or a person. Exercise the affected behavior.
   If capture/input tools are absent, record a manual validation step rather than
   presenting it as automated. Do not call the fully automated loop proven yet.
6. Fix any regression within scope and rerun affected checks. Have a person judge
   input responsiveness and play feel.

**Done when:** the change is reviewable, the relevant checks pass, evidence of the
visible result is retained, human feedback is recorded, and manual vs automated
steps are explicit. The resulting report should identify the bottleneck worth
automating next, not assume an editor bridge is necessary.

## 3 — Close measured gaps (proposed)

Evaluate editor/LSP/debugger integration and screenshot/input tooling only after
the first experiment. Prefer maintained, official interfaces where available.
Document version/OS support, installation, authentication, scope of filesystem
and process access, shutdown behavior, and reliable failure handling. Keep
services local by default and never open remote-control ports implicitly.

### Optional workflow hooks (proposed; not implemented)

After explicit tools and commands are proven, evaluate a small, opt-in OpenCode
plugin to coordinate preflight validation, asset previews/provenance, authorized
post-assembly checks, and completion summaries. See the
[hook plan and safeguards](FEATURES.md#7-opencode-plugin-hooks--optional-workflow-automation).
This is workflow automation, not a replacement for asset tools, tool-level
validation, OpenCode permissions, or human approval. No plugin is required for
the first asset milestone.

**Done when:** the target OpenCode V2 SDK's supported hooks are verified, the
workflow still works without the plugin, installation is previewable and opt-in,
and isolated tests cover scope filtering, duplicate events, recursion, timeout,
cancellation, permission denial, and validation failures. No hook may silently
authorize paid calls, uploads, overwrites, or game launches.

## Later — Broader asset creation and scene assembly (not implemented)

After the real-game loop is reliable, extend the static sprite slice into
animation, effects, tilesets, optional generation providers, and broader Godot
scene assembly. Include licensing and provenance
records, reproducible imports, collision/resource validation, and human
art-direction review. Concrete providers, asset formats, and integrations need
separate design and approval. Do not make any provider or paid API a prerequisite
for the core agent.

## References checked during initialization (2026-10-25)

- [OpenCode agents](https://opencode.ai/docs/agents/)
- [OpenCode config directories](https://opencode.ai/docs/config/)
- [OpenCode permissions](https://opencode.ai/docs/permissions/)
- [OpenCode CLI](https://opencode.ai/docs/cli/)
- [Godot CLI, stable](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
- [Godot CLI, 4.4](https://docs.godotengine.org/en/4.4/tutorials/editor/command_line_tutorial.html)

Recheck documentation for the actual installed versions before changing setup.
