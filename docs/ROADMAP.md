# Daydream — scope and next milestones

Internal milestones and acceptance criteria. For installation and everyday use,
see the [user README](../README.md).

**Last updated: 2026-11-05. Committed baseline: `ce9da22` (integrated review).
This update includes richer tile collisions and the validation recorded below.**

## START HERE NEXT — review and richer collisions delivered; next increment unselected

> **P0 and P1 are complete. The user confirmed both on 2026-11-04.
> Do not send them back through initial acceptance or treat the real-game trial
> as the next unstarted milestone. The selected P2 feature—integrated asset review,
> approval and separate import—is implemented and verified. The user then selected
> richer collisions for P3. Do not confuse that selection with editor-visible layouts.**

### Completed acceptance

- [x] **P0 — live OpenCode/TUI workflow:** user reports completion of the native
  tool, asset-preview, revision/approval/import and game-preview acceptance phase.
- [x] **P1 — authorized real-game integration:** user reports completion of the
  real-game trial described in milestone 2.

**Evidence attribution:** these completion states come from the user's explicit
confirmation, separately from the automated/graphical fixtures recorded below.
The game, engine versions, specific change, captures, commit and detailed feedback
were not supplied in that confirmation. Do not invent them or claim an independent
assistant review of the user's trial. Capturing those details is a handoff task,
not a reason to reopen the completed phases or ask the user to repeat them.

### P2 — integrated review and approval (IMPLEMENTED AND VERIFIED)

- [x] User selected the integrated review/approval experience for sprites,
  animations and tilesets, replacing the mandatory CLI approval step.
- [x] `/asset-review` and `/preview review`: exact-revision browser review, explicit
  approval, retained change requests or cancellation. Built-in `/review` is preserved.
- [x] Shared-core hash-bound status/feedback, immutable records and fresh approval
  after revisions. Requested changes block further approval/import of that candidate.
- [x] Separately displayed/confirmed import plan, bound to revision, paths, generated
  content and resulting index. Permission denial, cancellation and stale plans fail safely.
- [x] Python/Node regressions and actual isolated OpenCode TUI verification of
  approval, separate import, changes and cancellation. See the [dated evidence](validation/2026-11-05-asset-review.md).

### P3 — richer tile collisions (selected and implemented)

- User explicitly chose richer collisions, not the separate editor-visible-layout
  suggestion. Scope is reusable tileset collision authoring, review and Godot export.
- Shared convex polygon validation, half-pixel coordinates, multi-piece shapes,
  ramp presets and one-way platform/margin settings; no alpha-derived geometry.
- Typed native/CLI inputs, collision-layout overlays and exact settings in the
  review viewer; collision-only changes still need fresh revision approval.
- Existing solid-rectangle tiles, artifact sets and approval identities are
  preserved rather than automatically migrated. See [collisions](COLLISIONS.md).
- Real Godot tests verify ramp hit positions/normals, gaps and an actual character
  passing upward through a one-way platform then landing on it. Game-specific
  controller/play-feel acceptance is not implied by those synthetic checks.
- The actual graphical Godot collision render and coverage previews were inspected;
  see [the dated evidence](validation/2026-11-05-tile-collisions.md). Native tool
  discovery exposes the polygon and preset schemas. No existing game was modified.
- **Next user action:** manual collision/play-feel testing planned for 2026-11-06;
  not yet reported complete. Follow the [manual checklist](COLLISIONS.md#manual-test-checklist).
  Keep this new-feature acceptance distinct from the already completed P0/P1 trials.

### P4 — select the next product increment (NEXT; not selected)

Collect feedback on the delivered workflow and choose the next improvement with
the user. Editor-visible layouts remain a candidate, not an authorized task.
Retain original P0/P1 trial details when supplied without inventing or reopening
those completed trials. New-game controller testing needs explicit project scope.

**P4 exit criterion:** a bounded increment is selected, implemented in the shared
capability layer and validated with retained evidence.
Completed testing is not blanket authorization to edit the tested game, install
software, migrate an engine, connect a paid provider, or add an editor service.

## Progress snapshot — what is actually done

“Implemented” below means reusable code and documented interfaces exist; it does
not mean human acceptance or the full idea-to-playable product is complete.

| Area | Implemented now | Evidence / remaining boundary |
| --- | --- | --- |
| Product direction | Summer alternative for stock Godot/OpenCode, persisted in contributor and installable agent instructions; pinned public-source research | No Summer installation, closed-editor access, full parity claim, or copied implementation |
| Installation/startup | Preview-first non-overwriting launcher, agent, intro and native tools by default; explicit `--agent-only` exception | Installed launcher/session entry verified previously; no `--with-tools` flag is needed |
| Native tools | Typed sprite/animation/tileset actions, search/describe/call, structured results, shared Python backend and CLI, permission checks and cancellation | Actual loading/describe calls and isolated checks verified; P0/P1 complete per user confirmation |
| Static sprites | Pixel specs, bounded PNG ingestion, immutable edits, transparent images/previews, exact approval and Godot import | Unit/resource checks and image inspection; user confirms the overall acceptance phases complete, without per-asset details |
| Animation | Ordered clips, timing/loop/pivot, frame-revision assembly, atlas/APNG/contact/HTML previews, whole-animation approval and Godot resources | Real Godot ordering/timing/playback checks; P0/P1 user-confirmed, detailed motion feedback not yet recorded |
| Environment tiles | Editable tiles, 162 terrain/empty corner patterns, seam/layout previews, rectangles/convex pieces/ramps/one-way geometry and approved TileSet/TileMapLayer import | Terrain/layout/physics fixtures; richer-collision movement checks; game-specific play feel still requires its actual controller |
| User preview | Native `/preview` game/asset/status/stop UI, shared runtime service/RPC/tool, owned-process tracking, engine selection and browser viewer | Native/RPC status and graphical fixtures verified; user confirms live UI/real-game phases complete |
| Review and approval | `/asset-review` across all asset kinds; explicit decisions, retained feedback and separately confirmed exact import plans; no model-facing approval tool | Actual standalone TUI approval/import/change/cancel flow verified with synthetic assets; see dated evidence |
| Safety | Preview-before-apply, non-overwriting outputs/sidecars, project scope, exact-hash approval, no native auto-approval, no installs/permission widening | Tested in isolated fixtures; not an OS sandbox or authenticated proof of human review |

### Validation baseline

- Latest feature validation: **145 Python-discovered tests passed** in the isolated
  Pillow environment with Godot/ttfx checks enabled. The dependency-free run passed
  with **54 optional tests skipped**. Node adapter/viewer/review tests run through the suite.
- Separate graphical preview checks launched/stopped only an isolated synthetic
  Godot project. A synthetic tileset scene was also rendered; its actual viewport
  capture and numbered tile preview were inspected. These are not user-approved
  artwork or an existing-game playtest.
- Commands and fixture boundaries: [development](DEVELOPMENT.md). Prior temporary
  images/logs may disappear; do not treat their paths as durable acceptance reports
  or infer user acceptance from unit-test counts. P0/P1 completion is attributed
  to the user's confirmation, not those fixture results.
- Shipped feature commits: `7d3225d` native asset operations, `9d6e651` game/asset
  preview, and `fd8b5a4` environment tiles. This roadmap update does not itself
  authorize a new commit, push, installation or game-project change.

### Explicitly not finished / not part of the current bounded slice

- General prompt-to-image generation, hosted providers, automatic game/level design,
  Godot editor control, and broader effects/audio/3D asset creation.
- Animated tiles, hex/isometric terrain, automatic concave decomposition/alpha tracing,
  navigation, and layouts baked into editor cell data. The generated TileSet is
  editor-paintable; its companion example layout populates **at runtime**.
- Authenticated human identity, an OS sandbox, and review support for asset kinds
  not yet implemented. The integrated UI covers sprites, animations and tilesets;
  CLI approval remains a fallback and there is no model-facing approval tool.
- Portable screenshot/input automation and a fully autonomous verified game loop.
  No new provider/service/editor bridge is authorized merely because P0/P1 are done;
  select the next capability from user feedback in P4.

## Vision

Daydream is a **Summer Engine alternative for stock Godot and OpenCode**, not just
an instruction pack. Its product interface should expose typed, discoverable
workflow operations over reusable implementations, with both CLI and native
OpenCode tool access. Public Summer architecture is a reference to investigate,
not a requirement to copy its editor, paid backend, MCP transport, or permissions.

**Dream it. Make it playable.** Daydream aims to create sprites, effects, and
assets, then assemble them into playable Godot scenes. This is the product
direction, not a claim that generation or automated assembly works today.

See [features and enabling tools](FEATURES.md) for the proposed creative feature
set, candidate tools, and a first asset-creation milestone.

## Discoverable operation interface (implemented; P0/P1 user-confirmed complete)

- Pinned public-source [Summer architecture study](research/SUMMER_ARCHITECTURE.md),
  distinguishing implemented code from design claims and closed-editor behavior.
- Canonical typed catalog, structured results, CLI search/describe/call and a
  native V2 adapter included in the standard install over shared asset implementations.
  See [operations](OPERATIONS.md).
- Frame-revision assembly replaces per-game manual atlas/GIF composition for
  compatible inputs; existing game candidates are not migrated automatically.
- Native read/edit checks, adapter-owned logical file grants, non-writing previews,
  cancellation and bounded subprocess execution. No model-facing approval decisions;
  the user review UI uses the same shared backend with its own permission checks.
- Live OpenCode loading/discovery and describe execution verified after resolving
  the installed plugin symlink before locating the Python backend.
- User confirms live acceptance and real-game phases complete; detailed trial
  feedback/evidence can be retained in the P4 handoff. No claim of Summer parity or editor control.

## Interactive preview (implemented; P0/P1 user-confirmed complete)

- Native `/preview` picker with game, asset, status and owned-process stop actions.
- Shared runtime service behind RPC and a native tool; no model round trip or daemon.
- Godot 4 graphical launch with optional explicit engine pin, permission checks,
  bounded diagnostics, duplicate refusal and process cleanup on plugin unload.
- Hash-validated self-contained browser asset viewer with no approval/import effects.
- See [preview](PREVIEW.md) for remote-server behavior, test evidence and limits.

## Boundaries

- **Daydream:** reusable capability implementations, native tools/commands, CLI,
  agent instructions, tests and product documentation—not a game repository.
- **dotfiles:** optional global wiring only, added separately when authorized.
- **each game:** engine pin, controls, architecture, design intent, assets, tests,
  and its own `AGENTS.md`. A test game is not a global dependency.

Asset operations share a local Python implementation behind CLI and native
OpenCode V2 adapters; the existing plugin also owns the stateful preview service
and TUI command. No separate daemon, Godot addon, MCP endpoint, persistent
screenshot mechanism, or remote-control port is installed. Existing OpenCode
configuration remains the authority for tools and permissions. Future integrations
need their own permission/trust review.

## 0 — Starter (implemented)

- Installable Markdown agent with project discovery, scoped edits, validation,
  evidence boundaries, and human review in its workflow.
- Preview-first, non-overwriting installation of launcher, agent, native tools, and intro by
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

Installed agent/launcher entry and native plugin discovery have since been
verified separately. This milestone does **not** prove the agent can complete a
game change autonomously. The user confirms P0/P1 completion; the next handoff is
feedback and increment selection in P4, not a claim of full autonomous game creation.

## 1 — Static sprite workflow (implemented; P0/P1 user-confirmed complete)

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

The user confirms the overall acceptance phases are complete; the specific
artwork/change and feedback have not yet been documented here. Each future asset
still requires its own approval. Animation is covered in 1b; resize, provider
generation and full scene assembly remain outside this static slice.

## 1b — Frame-based animation extension (implemented; P0/P1 user-confirmed complete)

- Named, ordered clips built from static bases and pixel/patch-defined frames.
  Fixed canvas/palette and one explicit pivot; no automatic trimming or resizing.
- FPS, relative per-frame duration, looping, and a declared default animation.
- Hashed atlas, local APNG motion previews, contact sheets with pivot markers,
  and a local-only HTML viewer. One visual state uses a static PNG preview.
- Non-destructive frame/timing/loop/pivot revisions and whole-animation approval;
  a static sprite approval cannot approve an animation.
- Preview-first import as `SpriteFrames` plus nearest-filtered `AnimatedSprite2D`
  with explicit pivot and autoplay, without replacing game scenes or scripts.
- Real Godot checks cover frame regions/order/durations, looping progress, and a
  non-looping clip stopping on its last frame. Contact sheets have been read;
  the user confirms P0/P1 completion, with detailed motion feedback still to record.

See [animation usage, limits, and evidence](ANIMATIONS.md). No new image provider,
runtime service, package, interpolation system, or character controller is added.

## 1c — Environment tilesets (implemented; P0/P1 user-confirmed complete)

- Shared sprite-based tile creation/editing, 162-pattern two-terrain transitions
  including empty-map boundaries, exact compatible-edge checks and layout previews.
- Typed CLI/native operations and `/preview asset` integration, immutable revisions,
  whole-bundle approval and collision/terrain metadata bound to the exact hash.
- Non-overwriting Godot 4.3+ TileSet/corner-terrain/full-tile collision import;
  a reusable layer populates an approved explicit layout at runtime, not editor time.
- Real Godot terrain-painting, atlas, layer placement and physics ray-hit fixtures.
- User confirms the overall live/real-game acceptance phases are complete; record
  the trial details when provided in P4. This is not universal asset generation or level design.
  See [environment art](TILESETS.md).

## 2 — Prove the real game loop (complete per user confirmation, 2026-11-04)

P1 is complete according to the user. The following is the retained acceptance
procedure, not an instruction to repeat the trial. Project-specific evidence and
feedback should be captured in P4 when supplied.

On an authorized development machine with a trusted Godot project:

1. Install or manually wire the agent; verify `opencode debug agents` discovers it.
2. Capture a baseline: game commit/working changes, exact engine and OpenCode
   versions, test commands, and a reproducible scene/interaction.
3. Choose one small observable code or approved-sprite/animation/tileset change with
   acceptance criteria. No redesign, engine migration, or broader asset pipeline.
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

After the real-game loop is reliable, extend the sprite/animation slices into
effects, broader terrain features, optional generation providers, and broader Godot
scene assembly. Include licensing and provenance
records, reproducible imports, collision/resource validation, and human
art-direction review. Concrete providers, asset formats, and integrations need
separate design and approval. Do not make any provider or paid API a prerequisite
for the core agent.

## Reference starting points

- [OpenCode V2](https://opencode.ai/v2/docs/)
- [OpenCode V2 CLI](https://opencode.ai/v2/docs/cli)
- [Native plugin architecture](https://opencode.ai/v2/docs/build/plugins)
- [Server tools and permissions](https://opencode.ai/v2/docs/build/plugins/server)
- [TUI commands/dialogs](https://opencode.ai/v2/docs/build/plugins/cli)
- [Typed plugin RPC](https://opencode.ai/v2/docs/build/plugins/rpc)
- [Godot CLI, stable](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)
- [Godot TileSet](https://docs.godotengine.org/en/stable/classes/class_tileset.html)
- [Godot TileMapLayer](https://docs.godotengine.org/en/stable/classes/class_tilemaplayer.html)

Recheck documentation for the actual installed versions before changing setup.
