# Your assets

Use **`/assets`** to create, browse, preview, approve and add artwork to your project.
It works with sprites, animations and environment tiles.

The flow is **1. Create → 2. Review/revise → 3. Approve → 4. Add/update →
5. Preview**. Menus show the current step and highlight the next available action.
You can finish for now and resume from the candidate's saved state.

## 1. Create: describe what you want

Open `/assets` and choose **Describe a new asset…**, or ask Daydream in the chat:

> Create a small pixel-art slime named Moonlight Slime. Use a soft purple palette
> and show me a candidate before adding it to the game.

Use an ordinary name—spaces and capitals are fine. You do not need to choose
filenames or add version numbers. Describing an asset sends a request to your
current AI assistant; simply browsing the list does not.

When the candidate is ready, open `/assets` again.

## 2. Review or revise

### Pick a candidate

The list shows current candidates first. You can search by name, open a thumbnail
overview, look at older versions, or view assets already added to the project.

| Status | What it means |
| --- | --- |
| **Draft** | Ready for you to inspect; not approved yet |
| **Needs changes** | Your feedback was saved; choose **Make revised version** to proceed |
| **Approved** | You approved this version; adding it to the project is a separate step |
| **Imported** | Its files were added to the project; it may still need placement in a scene |
| **Modified outside Daydream** | Some added files changed or are missing; an update will not replace them |

### Preview and decide

Select the candidate and confirm opening its browser preview. Inspect the artwork
at the size you intend to use. For animation, watch it move. For tiles, look at
the arrangement, edges and collision outlines.

After a revision, open **Compare with previous version** in the browser. The
previous version appears on the left and the **New candidate** on the right, with
saved feedback beneath each. Use **Older version** to compare another earlier
candidate. **Artwork scale** zooms both sides equally, so changes are easy to judge.
On narrow screens the versions stack vertically.

The candidate under review stays fixed while you browse older versions. Approval
in `/assets` applies to that candidate, not the older reference. When reviewing
an older or already-approved candidate, its heading reads **Selected version**.
If a previous version is unavailable, the preview explains why.

Return to OpenCode and choose:

- **Approve artwork** when this version is ready, continuing to step 3.
- **Request changes** to save specific feedback.
- **Open preview again** to take another look.
- **Cancel / finish review** to leave without a new decision.

If asked for a **reviewer label**, enter your name or simply **`user`**. It records
who reviewed the artwork; it is not a login or an asset name.

### Make the revised version

After saving feedback, choose **Make revised version** in the same menu. Daydream
already knows which asset you selected and includes all its saved feedback. You
don't need to remember its name, enter a path, or compose another chat message.

The menu closes and sends a request to your current assistant. Follow its progress
in chat and answer any questions or tool-permission prompts. When the new candidate
is ready, open `/assets` to review it. The earlier version and feedback are kept;
the new version needs its own approval before adding it to your project.

To postpone the revision, choose **Cancel / finish review** instead. Your feedback
stays saved, and **Make revised version** is available when you reopen the candidate.

Forgot something or want to clarify an earlier note? Choose **Add more feedback**
before making the revision. Earlier notes are kept. **Read saved feedback**
shows everything recorded for that version. Repeating the same note doesn't add
a duplicate. The candidate remains **Needs changes** until Daydream prepares a
new version for you to review; adding more feedback does not approve it.

## 3. Approve the reviewed version

When satisfied, choose **Approve artwork**, enter your reviewer label and confirm
the review. Approval applies to the version you just viewed; a revised candidate
needs a new review.

The menu then highlights **Add or update in project** for step 4. Approval alone
does not add files to your game. If you finish for now, you can resume at step 4
when you reopen the approved candidate.

## 4. Add or update in your project

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

### Review the plan and confirm

Read the plain-language summary: are you adding separate files, or updating
something the game already uses?

Choose **Show technical details** only if you want the exact filenames and extra
information. Then choose **Add this asset** or **Apply this update** and confirm,
or choose **Keep staged / back** to postpone it.

If Daydream offers **Set up asset tracking**, allow it to keep track of assets in
this project. That setup does not add artwork or change gameplay.

## 5. Preview the result

When finished, choose:

- **Preview this scene** to run that standalone scene.
- **How to open it in Godot** for ordered manual steps and how to continue into your game.
- **Done** to return to your session.

Adding an asset does not automatically place it into a level, change your main
scene, or give it gameplay behavior. Ask for that separately:

> Place the approved Moonlight Slime in a separate test scene so I can check its
> size and animation. Keep the main level unchanged.

Next: [playtest](PREVIEW.md) · [make sprites and animations](SPRITE_WORKFLOW.md) ·
[create walls and floors](TILESETS.md) · [get help](TROUBLESHOOTING.md).
