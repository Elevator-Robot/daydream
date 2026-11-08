# Versions, history and updates

Daydream keeps previous versions so you can revise artwork without losing the
original. You manage them through **`/assets`**—you don't need to name folders
`v1`, `v2`, and so on.

## Find the version you want

The asset list normally shows the newest candidate for each asset. Choose
**Show older revisions** to see earlier candidates, then select one to preview it.
Choose **View imported assets** to see what has already been added to the project.

New candidate versions are stored out of the ordinary working art folders.
Existing older folders stay where they are. History is retained automatically,
but it still uses disk space and is not a substitute for a project backup.

## Should I add a copy or update?

| Choose | When to use it | Result |
| --- | --- | --- |
| **Add a separate copy** | New artwork, experiments, or preserving manually edited assets | New available filenames; existing scenes stay unchanged |
| **Update [asset name]** | Replace a previous Daydream asset that hasn't been edited elsewhere | Existing references use the new version; previous files are backed up |

You can use the same friendly name for a separate copy. Daydream handles filename
conflicts. Different assets still benefit from descriptive names such as “Shop
Floor” and “Forest Path.”

## Why is Update disabled?

Common reasons:

- The exact candidate is already imported; there is nothing new to apply.
- You changed or removed an imported file in Godot or another editor.
- The proposed change would alter how an existing asset is organized or used.

Your manual changes are protected. Choose **Add a separate copy**, compare the
results, and decide which version to use. Daydream does not merge manual edits
automatically.

Before an update, save and close editors working on that asset. Unsaved editor
changes cannot be detected.

## Use an older candidate again

1. Open `/assets` and choose **Show older revisions**.
2. Select the older candidate and inspect it.
3. Approve it if needed.
4. Choose **Add or update in project**.
5. Add a separate copy, or update the unchanged asset you intend to replace.
6. Read the summary and confirm.

This is a deliberate change, not an automatic undo. If you manually edited the
current asset, use a separate copy to preserve those edits.

## What happens when I edit in Godot?

Your saved edits remain in the Godot scene. They do not automatically become a
new Daydream candidate. If you want Daydream to build on them, explain what you
changed and agree on a new candidate rather than allowing a replacement blindly.

## Can I delete the old versions?

There is no automatic cleanup command yet. Do not remove versions or recovery
files while an update is in progress. If you want to reduce storage, ask Daydream
to inspect what is safe to remove and show you a cleanup plan first. Deletion
requires a separate decision; it is not part of approving new art.

If an update fails, keep the error message and ask Daydream to inspect the saved
recovery files before trying again. Avoid repeatedly pressing Apply or deleting
files to get past a refusal.

Back to [Your assets](REVIEW.md) · [Troubleshooting](TROUBLESHOOTING.md).
