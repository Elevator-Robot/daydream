# Make a sprite or animation

**Describe → Preview → Revise → Approve → Add → Playtest**

Before starting, [enable pixel-art creation](../README.md#enable-pixel-art-creation)
and open your game with `daydream /path/to/your/game`.

## Describe the sprite

Tell Daydream what it represents, how large it should be and what style it should
match. If you don't know the size or palette, ask for a recommendation first.

> Create a transparent 32×32 slime named Moonlight Slime. Use five colors that
> match the game's purple-and-green palette. Show me a candidate before adding it.

You can also ask Daydream to start from an existing small PNG. Name the file and
explain what you want changed. Keep the original available for comparison.

## Inspect it

Open `/assets`, select the candidate and confirm opening the preview.

- Can you recognize it at the size it will appear in the game?
- Do the colors, outline and shading fit the surrounding artwork?
- Are the edges sharp and the background transparent where intended?

The checkerboard behind a transparent sprite is only a viewing aid. It will not
appear in the exported artwork.

## Request a revision

Choose **Request changes** and enter what needs improving, for example:

> Make the outline darker and the eyes easier to read.

After saving the note, choose **Make revised version**. Daydream receives the
selected asset and all saved notes automatically. Follow progress in chat, then
return to `/assets` to review the result.

New candidates preserve the original. Use **Show older revisions** in `/assets`
when you want to inspect an earlier version.

## Add animation if needed

Skip this step for a static sprite. Otherwise, describe the motion:

> Give Moonlight Slime a four-frame idle animation with a slow blink. Keep its
> feet aligned and show me the motion before adding it.

Watch playback in the browser. Check the speed, loop transition and whether the
character seems to slide or jump between frames. A still image cannot show this.

For a revision:

> Slow down the blink and hold the eyes open longer. Save a new candidate.

Approving the original still sprite does not approve its animation. Review the
complete motion before choosing **Approve artwork**.

## Approve and add

In `/assets`:

1. Choose **Approve artwork** for the candidate you just inspected.
2. If prompted, enter your name or `user` as the reviewer label, then confirm.
3. Choose **Add or update in project**.
4. Use **Add a separate copy** for a new asset or experiment. Use **Update** only
   when you intend to change the existing Daydream asset named in the summary.
5. Review and separately confirm the change.

See [Your assets](REVIEW.md) for the full guided flow. You do not need to enter
filenames, version numbers or terminal approval commands.

## Test in Godot

Choose **How to open it in Godot** or **Preview this scene** after adding it.
Check the size, position, transparency and animation once more in the actual game
renderer. A standalone sprite scene won't have movement or gameplay behavior
unless you add it separately.

When ready, ask Daydream to place the approved asset into a specific test scene or
level. Keep that request small and say what should remain unchanged.

If something looks wrong, ask for another candidate and repeat the review. Your
previous version remains available. See [versions and updates](ASSET_LIFECYCLE.md)
before replacing a scene you have manually edited.
