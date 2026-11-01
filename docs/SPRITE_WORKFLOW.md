# The sprite workflow

Take a sprite from an idea to a reviewed asset in your Godot project:

**Describe → Create → Preview → Revise → Animate (optional) → Approve → Import → Test**

## Before you start

Enable the [optional sprite tools](../README.md#pixel-art-sprites-optional), then
open a trusted Godot project:

```sh
daydream /path/to/your/game
```

Use a throwaway project for your first test. Daydream currently works with
explicit pixel designs, not a general AI image-generation service.

## 1. Describe the sprite

Tell Daydream what it represents, its dimensions, and the style or palette to use.
Mention any existing artwork it needs to match.

> Create a transparent 32×32 slime using five colors. Match the existing game's
> pixel-art style. Show me a preview before importing anything.

**Result:** an agreed brief with clear size, palette, and appearance goals.

## 2. Create a candidate

Daydream creates an editable pixel design, a transparent PNG, and an enlarged
preview. You can also start from an existing palette-limited PNG.

**Result:** a new candidate version. Nothing is imported into the game yet.

## 3. Review the preview

Open the actual preview and check:

- Silhouette and readability at the intended size.
- Colors, outline, shading, and consistency with the game.
- Transparency and sharp pixel edges.

The enlarged preview uses a checkerboard to show transparency. That checkerboard
is not part of the exported sprite. A preview is not an in-game screenshot.

**Decision:** request changes or continue with this candidate. Creation alone
does not count as approval.

## 4. Revise without losing the original

Ask for specific changes:

> Make the outline darker and keep the original version. Show me the new preview.

Daydream saves a fresh revision rather than changing the original. Recoloring,
mirroring, pixel edits, and rectangle fills are supported. Compare the versions
and repeat this review/edit loop until you are satisfied.

**Result:** a clearly identified candidate to keep, with previous versions intact.

## 5. Add animation, if needed

Skip this step for a static sprite.

> Give this slime a four-frame idle animation. Keep its feet aligned. Show me
> the animation before importing it.

Agree on the named animation, frame order, timing, looping, and pivot. Daydream
provides a motion preview and a labeled contact sheet.

Watch the motion preview in a browser or APNG-capable viewer. Check the timing,
loop transition, and alignment. A contact sheet—or an image tool displaying only
the first frame—cannot establish that the animation moves correctly.

> Slow the blink down. Save a new version and keep the previous animation.

**Result:** a reviewed animation candidate. Approval of its original static
sprite does not approve the animation.

## 6. Approve an exact version

Tell Daydream which candidate you approve:

> I approve the darker-outline version. Use that exact revision.

For animation, approve the complete clip after watching it, including its timing
and looping. Daydream records approval for that exact revision. Changes to pixels,
frames, pivot, timing, looping, or previews require another review and approval.

**Result:** an approved candidate, not permission to make unrelated game changes.

## 7. Review and apply the import

Authorize adding the approved candidate:

> Show me where this approved sprite will be added, then import it as a standalone
> Godot scene. Don't replace existing assets or change the main scene.

Review the planned destinations before applying them. Daydream adds the approved
image and editable source, along with either a static `Sprite2D` scene or animated
`AnimatedSprite2D` scene. Existing assets are not overwritten; choose a new name
if a destination is already occupied.

**Result:** a reusable Godot asset. Import does not automatically place it in a
level, add movement/collisions, or build a character controller.

## 8. Test it in Godot

Open the generated scene and instance it in a test level. Check:

- Correct dimensions, transparency, colors, and sharp filtering.
- Position and pivot relative to the level and other artwork.
- For animation: frame order, timing, looping, and visible jitter.

Run project checks when authorized, but do not treat a passing headless check as
visual approval. If something looks wrong, return to the revision step; keep the
existing imported asset until you deliberately decide how to replace it.

**Done when:** you have reviewed the actual artwork/motion, approved the exact
candidate, inspected the import, and checked its appearance in Godot.

---

Command formats and limits: [static sprites](SPRITES.md) · [animations](ANIMATIONS.md).
