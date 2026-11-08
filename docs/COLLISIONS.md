# Walls, ramps and one-way platforms

Collision shapes decide where characters can move. Daydream can give tiles a full
blocking shape, a ramp, several separate solid pieces, a one-way platform, or no
collision at all.

## Describe the behavior

You do not need to enter polygon coordinates. Tell Daydream what the player should
be able to do:

> Make this slope walkable, rising to the right. Keep the artwork unchanged and
> show me the new collision preview.

> Make this ledge a thin one-way platform: the player should jump through it from
> below and land on it from above.

> The doorway should stay open. Put solid collision on the two sides, not across
> the gap.

Collision changes create a new candidate. They do not replace the previous version
or become approved simply because the picture stayed the same.

## Review the shapes

Open `/assets`, select the new candidate and open its preview.

- **Yellow** marks ordinary solid collision shapes.
- **Cyan** marks one-way collision shapes.
- An empty area should have no blocking shape when it is meant to be walkable.

Look at collision coverage over the layout as well as the individual tiles. Make
sure the ramp faces the correct direction and the shape matches the intended
playable surface. The color overlay is for review; it is not part of the artwork.

Approve the candidate, then separately choose **Add or update in project**. Use a
separate copy for an experiment, or explicitly update an unchanged Daydream asset.
See [Your assets](REVIEW.md) for the full add/update flow.

## Manual test checklist

Test in a separate scene first, with the character you actually intend to use.
Ask Daydream to prepare a small test area if needed, without changing the main level.

1. Walk both directions over each ramp. Look for snagging, bouncing or falling through.
2. Jump upward through a one-way platform, then land on it from above.
3. Walk through a gap that is wide enough for the character.
4. Check that decorative, nonblocking tiles do not stop movement.
5. Check that ordinary floors and walls still block where intended.
6. Use `/preview status` for messages and `/preview stop` when finished.

If something feels wrong, report the location, movement direction and character
used. A screenshot or short recording helps. Changing only the collision still
requires review and approval before applying the new candidate.

## Keep in mind

Characters of different sizes and speeds can behave differently on the same tiles.
A ramp may also require suitable movement settings in the game's character code.
Daydream's tile editing does not automatically add or replace that movement code.

Simple custom shapes can be built from several pieces. There is no drawing tool
for editing vertices in the preview window and no automatic tracing of transparent
artwork. Describe the intended behavior and inspect the proposed result.

Back to [walls and floors](TILESETS.md) · [Your assets](REVIEW.md).
