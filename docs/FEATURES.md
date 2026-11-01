# Daydream — features and enabling tools

Internal feature planning. For installation and everyday use, see the
[user README](../README.md).

**Dream it. Make it playable.**

This separates the creative feature plan from implemented slices. Daydream now
provides agent instructions, safe installation/launching, bounded Godot checks,
and a first [static sprite create/edit/approve/import workflow](SPRITES.md).
General image generation, animation, editor control, and full scene/game assembly
are **not implemented**. PNG preview inspection is not graphical Godot validation.
OpenCode plugin hooks are also planned, not implemented.

Project-local [configuration initialization](PROJECT_CONFIG.md) is implemented:
the helper creates versioned location hints and an empty asset metadata container
without overwrites. The sprite helper now validates its own pixel specifications,
revision/provenance hashes, and approval records. Initialization alone does not
provide these checks, and other asset types remain proposed.

See [ROADMAP.md](ROADMAP.md) for sequencing and acceptance of the existing game
development loop. This document does not authorize installing software, choosing
paid services, or implementing integrations without their own review.

## Target workflow

1. Describe a game object, environment, or effect.
2. Agree on style, dimensions, palette, animation needs, and acceptance criteria.
3. Generate or draw editable assets in a staging directory.
4. Preview the result and let the user approve or request revisions.
5. Import approved assets into the game's existing layout.
6. Assemble Godot resources and scenes, with collisions and behavior as needed.
7. Run checks, inspect the graphical result, and playtest.

Start with **2D pixel-art games**. Broader 2D styles, audio, and 3D can follow;
do not try to build every pipeline at once.

## Feature map

Rows marked **initial slice** have bounded static functionality; their broader
target behaviors are not all implemented. Other rows are proposed. “Tools needed”
describes target capabilities, not packages already installed or selected.

| Feature | What the user should be able to request | Tools or components needed | Acceptance check |
| --- | --- | --- | --- |
| Pixel-art creation — initial slice | “Make a 32×32 slime using this palette.” | Editable pixel-grid JSON, local PNG export, palette/alpha validation, enlarged nearest-neighbor preview | Dimensions/palette/transparency checked; human silhouette approval still required |
| Sprite editing — initial slice | Recolor, mirror, paint pixels, or fill a rectangle; resize is still planned | Pillow, fresh revision bundles, protected source copies | Only requested pixels/properties change; originals and their approvals are preserved |
| Sprite animation | Idle, walk, attack, and hit animations | Frame editing, sprite-sheet packing, timing/loop metadata, playback preview | Consistent canvas/pivot, correct order and timing, no frame jitter |
| Tilesets and terrain | Ground, walls, corners, and transitions | Tile atlas builder, seam preview, Godot `TileSet` and terrain configuration | Tiles join without visible seams and terrain connections work in-engine |
| Backgrounds and props | Layered scenery, decorations, and parallax | Image creation/editing, layer export, composition preview, Godot scene templates | Consistent style and scale; layers align and scroll correctly |
| Visual effects | Sparks, smoke, explosions, magic, and trails | Flipbook tooling, Godot particle resources, shader templates, graphical preview | Effect looks right in motion, cleans up, and meets a project-defined performance budget |
| UI assets | Icons, panels, buttons, and HUD elements | Pixel/vector drawing, scalable panel rules, Godot `Control`/`Theme` resources | Readable at target resolutions; focus, scaling, and interaction work |
| Asset import — initial slice | Bring an approved static sprite into the game | Hash-bound approval, preview-first PNG/source/scene writes, provenance records, nearest-filtered `Sprite2D` | No overwrites; real fixture import/startup checked; graphical review remains pending |
| Scene assembly | “Turn this sprite into a playable character.” | Version-aware scene/resource writer, reusable node templates, input/collision wiring | Scene opens, references resolve, movement and collisions work in a graphical run |
| Level assembly | Build a small room from approved tiles and props | Layout specification, tile placement, spawn/exit markers, collision/navigation checks | Room is traversable; scale, collision, and entry/exit behavior are reviewed |
| Visual iteration | “The outline is too thick; make the impact brighter.” | Screenshot/frame capture, image viewing, before/after comparison, bounded revision workflow | Evidence shows the requested change; user approves the result |
| Audio (later) | Short sound effects, ambience, or music loops | Approved audio source/generator, conversion, waveform/listening preview, Godot playback resources | Suitable license, clean playback, correct looping, acceptable volume |
| 3D assets (later) | Simple models, materials, rigs, and animations | Modeling/export tooling, glTF validation, material/rig preview, Godot import checks | Correct scale, orientation, materials, animations, and runtime behavior |

## Tools and infrastructure to add

### 1. Asset specification and style contract — required

- A small, versioned asset specification: name, purpose, dimensions, palette,
  transparency, pivot, frame names/timings, and intended Godot resource type.
- A game-owned style guide with approved examples and explicit constraints.
- Validation with useful errors before generating or importing anything.
- Keep game-specific paths and conventions in that game's configuration, not
  hardcoded into Daydream's global agent.

### 2. Pixel/image creation and editing — required capability

- A deterministic drawing route for primitives, outlines, fills, palettes, and
  frame edits. This should work without an image-generation API.
- **Pillow** is now the optional static-sprite dependency, approved separately and
  tested in an isolated environment. The normal installer/core helpers remain
  standard-library-only. Sprite-sheet assembly is not implemented yet.
- Candidate: **Aseprite** for editable pixel-art sources and batch exports, when
  the user already has an appropriately licensed copy. **LibreSprite** is another
  candidate to evaluate; do not assume identical automation support.
- Optional AI image generation through a separately selected local or hosted
  provider. Evaluate transparency, palette control, reference-image support,
  consistency, cost, usage rights, and credential handling first.
- Generated artwork still needs pixel cleanup and art-direction review. General
  image generation does not guarantee clean pixel art or consistent animation.

### 3. Preview and approval — required

- Contact sheets, enlarged pixel previews, animation playback, and tile seam
  previews before assets enter a real game.
- An image-viewing route the active agent can actually access. Writing a PNG is
  not proof the agent has seen it.
- Graphical Godot runs and screenshot capture for scene/effect review. Choose
  desktop-specific capture tools only after checking the target environment.
- Manual review as a supported fallback; never claim visual validation from a
  successful headless check alone.

### 4. Godot import and scene/resource construction — required

- Small local helpers built on documented Godot interfaces; initially prefer
  files and bounded CLI invocations over a persistent service.
- Version-aware creation of `.tscn`/`.tres` resources, resolving existing paths
  and UIDs without rewriting unrelated scenes or inventing resource identities.
- Templates for `Sprite2D`, `AnimatedSprite2D`/`SpriteFrames`, `CharacterBody2D`,
  collision shapes, particles, and UI; expand only with tested examples.
- Explicit pixel-art import settings and validation after Godot reimport.
- Use the existing `scripts/check_project.py` for import/smoke checks, alongside
  new resource-specific tests and graphical review. It is not an asset pipeline.
- An editor plugin or bridge is optional, not a prerequisite. Add one only when
  a measured limitation justifies a separately reviewed design.

### 5. Asset provenance and safe writes — required

- An asset manifest recording source, creator/provider, model/version when
  applicable, prompt/settings/seed when available, license/usage restrictions,
  output hashes, and approval status. Record unknowns rather than guessing rights.
- Staged outputs, previewable change plans, collision refusal, and explicit
  approval before replacing existing game assets.
- Preserve editable sources and originals. Keep previews and temporary artifacts
  separate from runtime assets; document how to undo each import.
- No secrets in manifests or Git. External uploads, paid generation, and model
  downloads need explicit authorization; seeds do not guarantee reproducibility
  across providers, model versions, or hardware.

### 6. Automated validation — required

- Fixture assets for dimensions, transparency, palette limits, frame counts,
  atlas bounds, path traversal, and overwrite refusal.
- Isolated Godot projects for scene/resource import, animation references,
  collisions, and missing-file failures; never test against an actual game
  without permission.
- Graphical checks for filtering, pivots, seams, shader/particle appearance, and
  frame timing. Human review remains the authority for style and play feel.
- Optional gameplay input automation only after its permissions, supported
  environment, and stop/timeout behavior are documented.

### 7. OpenCode plugin hooks — optional workflow automation

**Tools perform the work; hooks coordinate checks around that work.** Build and
test explicit asset/scene tools and commands first. Then add a small, opt-in
OpenCode plugin where hooks remove repeated manual coordination. The workflow
must remain usable without it; this is not a Godot editor plugin or MCP server.

Proposed lifecycle behavior (not committed SDK event names):

| When | Proposed hook behavior | Boundary |
| --- | --- | --- |
| Before a Daydream asset tool runs | Validate the asset specification, dimensions, palette, output paths, and required approvals | Reject invalid requests before writes; do not infer approval |
| After successful asset creation | Validate image/frame properties, build previews, and update provenance records | Only process declared outputs; do not import unapproved artwork |
| After scene assembly | Run resource checks and, when authorized, bounded Godot import/smoke checks | Godot execution is not read-only; retain logs and distinguish failures from unrun checks |
| When an operation finishes | Summarize changed assets, check results, and outstanding visual review | Report observed evidence only; finishing is not approval or visual verification |

Implementation requirements:

- Verify supported lifecycle hooks against the targeted OpenCode V2 plugin SDK
  before choosing event names or writing an adapter. Scope handlers to Daydream
  operations rather than every tool invocation in a session.
- Keep validation and overwrite protection inside the tools themselves too.
  Hooks are convenience automation, not a security boundary or a replacement for
  OpenCode permissions.
- Keep installation previewable and opt-in. Document plugin/runtime dependencies
  separately; do not silently expand installation with workflow services.
- Require authorization for paid generation, uploads, overwrites, and game
  launches. Hooks must not broaden an operation's approved scope.
- Use operation IDs and output hashes to avoid duplicate processing. Bound work
  with timeouts, prevent recursive hook triggers, and do not auto-retry edits or
  start an unbounded generate/validate/fix loop.
- Surface failures and timeouts explicitly. Failed validation must prevent a
  subsequent automated import; missing graphical access leaves visual review
  pending. Do not silently repair assets or mark them approved.
- Test unrelated-tool no-ops, repeated events, cancellation, permission denial,
  timeouts, validation failures, and recursion prevention in isolation before
  enabling hooks in a game.

Reference: [OpenCode V2 plugins](https://opencode.ai/v2/docs/build/plugins).
Exact hook coverage and failure/approval behavior need verification during the
plugin design; this table describes intended behavior, not existing SDK support.

## First static asset slice — implemented tools, acceptance still partial

The authorized first slice is intentionally static rather than animated:

> Create a palette-limited 32×32 slime, preview a darker-outline revision for
> approval, then import an approved static Godot scene.

Deliverables:

- [x] Versioned pixel specification, palette, and editable source.
- [x] Local PNG rendering and non-destructive recolor/mirror/pixel/rectangle edits.
- [x] Enlarged nearest-neighbor previews, actually read for the sample revision.
- [x] Hashed revision/provenance metadata and an explicit approval-record action.
- [x] Preview-first static PNG/source/scene import into an isolated fixture.
- [x] Standalone nearest-filtered `Sprite2D` resource, checked in real Godot.
- [x] Unit tests, tamper/collision checks, and real-engine import/smoke checks.
- [x] Recovery limits and manual, non-destructive undo guidance.
- [ ] User art-direction approval and a graphical Godot review in a real game.
- [ ] Animation frames, contact sheets, `SpriteFrames`, and `AnimatedSprite2D`.

**Not needed for this slice:** a paid image API, a local diffusion service, an
MCP server, an editor-control daemon, 3D generation, or a complete game generator.
Automatic plugin hooks are not required either: prove the explicit tools first.

After human/real-game acceptance of the static slice, add animation, then a
tileset and small level, then particles/shaders. Add optional providers only when they
improve a measured weakness in quality or workflow.
