# Troubleshooting

If something fails, keep the full message and tell Daydream which step you were
on. Error dialogs remain visible until dismissed. A screenshot helps when the
problem is visual.

## I can't find `/assets` or `/preview`

1. Restart OpenCode and open a session in your game project.
2. If the commands are still missing, return to the Daydream folder and run:

   ```sh
   python3 scripts/install.py
   python3 scripts/install.py --apply
   ```

3. Restart OpenCode again.

Use the standard installation for the complete experience. An **agent-only**
installation does not include these commands.

Use `/assets` for artwork. `/review` is OpenCode's code-review command.

## `daydream: command not found`

Make sure installation completed, then try:

```sh
export PATH="$HOME/.local/bin:$PATH"
daydream --doctor
```

If that works, add the PATH entry to your shell's startup configuration so it is
available in new terminals too.

## Pixel-art creation says a dependency is missing

Complete [Enable pixel-art creation](../README.md#enable-pixel-art-creation) in the
Daydream folder, then restart OpenCode. This setup is only needed once.

## `/assets` shows nothing

Create a candidate first: choose **Describe a new asset…** or ask Daydream in chat.
Then reopen `/assets`. If you expect an older asset, try **Show older revisions**.
For artwork saved somewhere unusual, ask Daydream to locate the candidate and
open the correct project.

## What is a reviewer label?

It's the name recorded with your approval or feedback. Enter your name or simply
**`user`**. It is not a login, password, filename or asset name.

## A name or existing-file error appears

In the guided flow, use **Add a separate copy**. Keep the friendly name or enter
another ordinary name; Daydream chooses available filenames automatically.

Use **Update [asset name]** only when you intend to replace that existing asset.
Don't delete files to get past an error. If an unexpected naming error remains,
copy the exact message and the name you entered.

## Update is disabled or says files were modified

Daydream detected saved changes or missing files, or the selected version is
already imported. Manual work is protected. Use **Add a separate copy** and compare
the results rather than resetting or deleting the existing asset.

Save and close relevant Godot scenes before updates. Unsaved editor changes
cannot be detected. Read [versions and updates](ASSET_LIFECYCLE.md) for more.

## The plan changed, or the review expired

Reopen `/assets`, select the candidate and prepare a fresh plan. Read it before
applying. Another change, a long pause or a restart can make an earlier plan stale.
An approval you already confirmed is retained if the artwork itself is unchanged.

## I already left feedback but want to add or correct it

Open the same candidate in `/assets` and choose **Add more feedback**. Use
**Read saved feedback** to see earlier notes. A clarification can say which earlier
instruction it changes; the history is retained rather than replaced.

If you see the older “Feedback already exists” refusal, update/restart Daydream
and reopen the candidate. Don't delete your notes or add a copy to bypass it.
Choose **Make revised version** to send the selected asset and all saved notes
to Daydream.

## I saved feedback, but nothing is being revised

Choose **Make revised version** in the candidate's review menu. Saving a note keeps
the menu open so you can add more feedback before starting. If you already closed
it, reopen the candidate in `/assets` and choose **Make revised version** there.
You don't need to type its name into chat.

The request appears in chat, where you can follow progress and answer questions
or tool-permission prompts. If sending fails, check chat before trying again to
avoid sending the same request twice. If the action is missing, update/restart
Daydream and reopen `/assets`.

## Godot isn't found, or its version doesn't match

Ask Daydream:

> Check which Godot version this project expects and which installed editor is
> available. Help me fix setup without upgrading the project or installing anything
> without asking.

The normal asset flow finds Godot automatically. A project needing a particular
editor may need one-time setup; you should not have to enter a path for each asset.

## The game won't open

Run `/preview status` and copy the recent messages. Make sure the project has a
starting scene selected in Godot. If another preview is running, stop it with
`/preview stop` before trying a different scene.

For a newly added asset, choose **Preview this scene** or open that scene in Godot
and press **F6**. `/preview game` runs the game's normal starting scene.

## The layout is empty in the editor but appears when playing

It may use the older runtime layout option. Add a separate copy with
**Editor-visible cells** if you want to paint it before playing. See
[editing layouts in Godot](EDITOR_LAYOUTS.md).

## An add/update was interrupted

Stop and keep the error message. Ask Daydream to inspect what changed and the
available recovery files before continuing. Don't repeatedly apply, remove old
versions, or delete files to force a retry.

## The intro doesn't appear

The opening animation is optional. Use `daydream --no-intro` to start without it.
It requires `ttfx` to be installed, but Daydream's asset and coding workflows do not.

Back to [getting started](../README.md) · [Your assets](REVIEW.md).
