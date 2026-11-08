# Sprite animation — first slice

Contributor/integration reference. User instructions are in [sprites and animations](SPRITE_WORKFLOW.md).

Scope: build a bounded, named animation from static pixel-art frames, review its
motion, and import an approved `SpriteFrames` resource and `AnimatedSprite2D`
scene. It extends—not replaces—the static [sprite workflow](SPRITES.md).

## Design and limits

- Reuse the optional Pillow environment. No provider, paid API, additional image
  library, editor plugin, service, or software installation is required.
- Create from an existing static revision plus a data-only JSON recipe. Frames
  are copies, pixel-row replacements, or bounded edits of that common base.
- A canonical animation source embeds every frame, uses one shared palette and
  canvas, and declares a single integer pivot. No implicit resizing, trimming,
  per-frame offset guessing, or interpolation hides alignment problems.
- Bounds: canvas up to 128×128; 32 unique frames; 8 named animations; 64 timeline
  steps per animation and 128 total; 20–5000 ms per step and 30 seconds per clip.
  FPS and relative durations follow Godot's `duration / fps` semantics.
- Each immutable bundle contains canonical source, a deterministic spritesheet,
  per-clip animated PNGs and labeled contact sheets, and a local HTML viewer.
  The viewer references only generated local images and makes no network calls.
- Contact sheets mark the shared pivot for alignment review. Motion previews
  preserve declared timing and looping; they are previews, not Godot screenshots.
- Revisions and approval include **all** frames, timing, pivot, loop flags, and
  preview files. Any change invalidates the old approval. Existing static
  approval files remain unchanged and valid for static imports only.
- Import previews first, refuses collisions/sidecars, archives editable source,
  and uses the same protected manifest update as static sprites. It writes a
  PNG atlas, `SpriteFrames` resource, and nearest-filtered `AnimatedSprite2D`
  scene with an explicit pivot. It does not change the game's main scene/code.

Headless checks can establish resources, frame order/durations, and playback
progress—not animation quality, visual smoothness, or human art approval. The
agent must ask the user to review actual motion before recording approval.

## Create a four-frame idle

Use the same optional setup as static sprites:

```sh
python3 -m venv .venv-sprites
.venv-sprites/bin/python -m pip install -r requirements-sprites.txt
```

From the Daydream checkout, choose new source directories in the game's normal
art layout. These example paths assume its default configuration:

```sh
PY=.venv-sprites/bin/python
GAME=/absolute/path/to/your/game
BASE="$GAME/art/sprites/slime-v1"
IDLE="$GAME/art/sprites/slime-idle-v1"

# Create a base if you do not already have a static revision.
$PY scripts/sprites.py create examples/slime.sprite.json --output "$BASE"
$PY scripts/sprites.py create examples/slime.sprite.json --output "$BASE" --apply

# Preview, then create the animation candidate. No approval is inferred.
$PY scripts/animations.py create examples/slime-idle.animation.json --base "$BASE" --output "$IDLE"
$PY scripts/animations.py create examples/slime-idle.animation.json --base "$BASE" --output "$IDLE" --apply
$PY scripts/animations.py inspect "$IDLE"
```

Open the emitted `preview.html` in a browser, or open `idle.motion.png` in an
APNG-capable viewer. The sample holds its eyes open for 1.5 seconds, then blinks;
wait for that initial hold before deciding it is static. `idle.contact.png`
shows all four ordered steps, durations, and the common pivot. `spritesheet.png`
is the transparent runtime atlas, without checkerboards or pivot markers.

The HTML viewer has no scripts, external fonts, remote URLs, or server dependency.
Reload it to replay a non-looping clip. Some image-reading tools show only an
APNG's first frame; never call that motion review. The preview encodes integer
milliseconds, within 1 ms of each declared frame duration. Godot retains the
original FPS and relative duration values.

Adjacent visually identical steps are coalesced only in the motion preview by
summing their holds. The source/Godot timeline keeps the original steps/order.
If every visual frame is identical, Pillow writes a static PNG with no playback
metadata; `inspect` reports `visual_frames: 1`. Source/Godot timing and looping
are still preserved, but there is no visible motion to judge from that preview.

## Recipe format

```json
{
  "schema_version": 1,
  "name": "slime_idle",
  "pivot": [16, 30],
  "frames": [
    { "id": "open" },
    {
      "id": "blink",
      "patch": {
        "schema_version": 1,
        "operations": [
          { "op": "rect", "box": [10, 16, 13, 19], "symbol": "g" }
        ]
      }
    }
  ],
  "animations": [
    {
      "name": "idle",
      "fps": 8,
      "loop": true,
      "frames": [
        { "frame": "open", "duration": 12 },
        { "frame": "blink", "duration": 1 }
      ]
    }
  ],
  "default_animation": "idle"
}
```

Every frame starts from the same static base; patches are not accidentally
accumulated from the previous frame. A frame can instead provide complete
`pixels` rows using the shared palette. IDs/names are unique lowercase slugs.
The recipe contains no file references or executable code; the only external
base is the explicit `--base` argument.

`duration` is relative: `duration / fps` gives seconds. For example, duration
`0.8` at `8` FPS displays for 100 ms. Loop flags must be booleans. There is no
ping-pong mode, per-frame pivot, automatic in-between generation, skeleton,
controller, or gameplay state machine in this slice.

## Revise and approve motion

```sh
NEXT="$GAME/art/sprites/slime-idle-v2"
$PY scripts/animations.py edit "$IDLE" --patch examples/slime-slower.animation-edit.json --output "$NEXT"
$PY scripts/animations.py edit "$IDLE" --patch examples/slime-slower.animation-edit.json --output "$NEXT" --apply
$PY scripts/animations.py inspect "$NEXT"
```

Edit files contain `schema_version: 1` and 1–128 `operations`:

- `frame`: existing `id` plus a static sprite `patch` for that frame's pixels.
- `recolor`: `symbol`/`color`, applied to every frame to retain palette consistency.
- `animation`: `value` containing a complete named clip; replaces that clip or
  adds a new one. This edits ordering, FPS, relative durations, and loop behavior.
- `pivot`: `value: [x, y]`, applied consistently to the whole asset.
- `default`: `animation` naming the default clip.

To rebuild the imported canonical source later, use `create source.json --output
NEW` **without** `--base`. All pixels/clips are embedded in that archive; no
original static base path is required. The rebuilt revision is not approved.

After the user has reviewed the exact candidate in motion:

```sh
$PY scripts/animations.py approve "$NEXT" --revision-hash HASH_FROM_INSPECT --reviewer user
$PY scripts/animations.py approve "$NEXT" --revision-hash HASH_FROM_INSPECT --reviewer user --apply
```

Animation approval is version 2 and binds the revision hash plus **every artifact
hash**, including all preview files. Static version-1 approval is not accepted.
Timing, pivot, loop, pixel, or preview changes require a new review. Reviewer
labels are local audit data, not authenticated identity or automated visual
acceptance. Unknown licensing remains `null` rather than being invented.

## Import into Godot

Initialize the game's project metadata if needed, previewing before applying:

```sh
python3 scripts/init_project.py "$GAME"
python3 scripts/init_project.py "$GAME" --apply
$PY scripts/animations.py import "$NEXT" "$GAME"
$PY scripts/animations.py import "$NEXT" "$GAME" --apply
```

The default output paths use configured asset/source roots:

- `assets/sprites/slime_idle.png`: transparent atlas.
- `assets/sprites/slime_idle.frames.tres`: named `SpriteFrames`, atlas regions,
  frame order, durations, FPS, and looping.
- `assets/sprites/slime_idle.tscn`: nearest-filtered `AnimatedSprite2D`, explicit
  pivot offset, and autoplay of the declared default animation.
- `art/sprites/slime_idle.json`: complete editable canonical source.
- A `sprite_animation` record appended to `.daydream/assets.json`.

`centered = false` and `offset = -pivot` keep every frame aligned to the same node
origin. The helper does not guess foot positions, place the node in a level, or
modify an existing game scene/script. Use `--destination` for another runtime
directory or a fresh `--name` to avoid collisions. Existing files and sidecars
are refused; the static workflow's lock, manifest checks, partial-failure
recovery, and manual undo boundaries also apply.

## Validation and remaining acceptance

```sh
.venv-sprites/bin/python -m unittest discover -s tests -p 'test_animations.py' -v
GODOT_BIN=/path/to/godot .venv-sprites/bin/python -m unittest discover -s tests -v
```

The implementation was tested with Pillow 12.3.0 and Godot 4.7.2. Tests cover
schema/resource bounds, palette/canvas mismatch, ordered clips, timing and loop
metadata, identical visual holds, revisions, approval invalidation, stale/cross-
type approvals, tampered previews, collision refusal, and the complete CLI flow.
Real Godot checks verify atlas regions, relative durations, nearest filtering,
pivot, looping frame progress, and non-loop playback stopping at its last frame.

The sample and slower contact sheets and transparent atlas were actually read.
This is not a claim of watching the browser animation, seeing a graphical Godot
run, or obtaining user art approval. Those remain human acceptance steps. Keep
complete revision bundles; preview-renderer/library changes can require a fresh
candidate and review rather than silently adopting old approval records.

References: [Godot SpriteFrames](https://docs.godotengine.org/en/stable/classes/class_spriteframes.html)
and [AnimatedSprite2D](https://docs.godotengine.org/en/stable/classes/class_animatedsprite2d.html).
