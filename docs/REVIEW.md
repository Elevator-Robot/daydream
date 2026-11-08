# Your assets

Use **`/assets`** to create, browse, preview, approve and add artwork to your project.
It works with sprites, animations and environment tiles.

## 1. Describe what you want

Open `/assets` and choose **Describe a new asset…**, or ask Daydream in the chat:

> Create a small pixel-art slime named Moonlight Slime. Use a soft purple palette
> and show me a candidate before adding it to the game.

Use an ordinary name—spaces and capitals are fine. You do not need to choose
filenames or add version numbers. Describing an asset sends a request to your
current AI assistant; simply browsing the list does not.

When the candidate is ready, open `/assets` again.

## 2. Pick an asset

The list shows current candidates first. You can search by name, open a thumbnail
overview, look at older versions, or view assets already added to the project.

| Status | What it means |
| --- | --- |
| **Draft** | Ready for you to inspect; not approved yet |
| **Needs changes** | Your feedback was saved; ask Daydream for a revised candidate |
| **Approved** | You approved this version; adding it to the project is a separate step |
| **Imported** | Its files were added to the project; it may still need placement in a scene |
| **Modified outside Daydream** | Some added files changed or are missing; an update will not replace them |

## 3. Preview and decide

Select the candidate and confirm opening its browser preview. Inspect the artwork
at the size you intend to use. For animation, watch it move. For tiles, look at
the arrangement, edges and collision outlines.

Return to OpenCode and choose:

- **Approve artwork** when this version is ready.
- **Request changes** to save specific feedback.
- **Open preview again** to take another look.
- **Cancel / finish review** to leave without a new decision.

If asked for a **reviewer label**, enter your name or simply **`user`**. It records
who reviewed the artwork; it is not a login or an asset name.

Approval applies to the version you just viewed. Approving it does **not** add it
to your game yet. A revised candidate needs a new review.

If you request changes, ask Daydream to act on them:

> Update Moonlight Slime using my saved feedback. Show me the new candidate.

Saving feedback alone does not start another generation request.

## 4. Choose how to add it

After approval, choose **Add or update in project**.

### Add a separate copy

Use this for a new asset, an experiment, or when you want to keep existing artwork.
Keep the displayed name or enter another friendly name. Daydream chooses available
filenames automatically. You do not need to resolve duplicate names yourself.

### Update an existing asset

Use **Update [asset name]** when you intend to change an asset already added by
Daydream. Scenes that use it will see the new version. A copy of the previous
files is retained first.

Save and close any Godot scene you are editing before updating it. Daydream can
detect saved file changes, but not unsaved work in an editor. If Update is disabled,
use **Add a separate copy** rather than discarding your edits. See
[versions and updates](ASSET_LIFECYCLE.md).

For a new tile layout, choose **Editor-visible cells** if you want to paint it in
Godot before playing. Daydream finds Godot for you. See [editing layouts](EDITOR_LAYOUTS.md).

## 5. Confirm the change

Read the plain-language summary: are you adding separate files, or updating
something the game already uses?

Choose **Show technical details** only if you want the exact filenames and extra
information. Then choose **Add this asset** or **Apply this update** and confirm,
or choose **Keep staged / back** to postpone it.

If Daydream offers **Set up asset tracking**, allow it to keep track of assets in
this project. That setup does not add artwork or change gameplay.

## 6. Open it or try it

When finished, choose:

- **How to open it in Godot** for the new scene's location.
- **Preview this scene** to run that standalone scene.
- **Done** to return to your session.

Adding an asset does not automatically place it into a level, change your main
scene, or give it gameplay behavior. Ask for that separately:

> Place the approved Moonlight Slime in a separate test scene so I can check its
> size and animation. Keep the main level unchanged.

Next: [playtest](PREVIEW.md) · [make sprites and animations](SPRITE_WORKFLOW.md) ·
[create walls and floors](TILESETS.md) · [get help](TROUBLESHOOTING.md).
