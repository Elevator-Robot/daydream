# Edit generated tile layouts in Godot

Choose **Editor-visible cells** when you want a generated tile layout to appear
in Godot's editor immediately, so you can paint and erase tiles before playing.
This feature needs Godot **4.3 or newer**, matching your game.

## Create and add the layout

1. Ask Daydream for a tileset with a small placed layout:

   > Create a mossy stone floor named Shop Floor. Show me a small room layout so
   > I can review the repeated tiles, corners and wall collisions.

2. Open `/assets`, select the candidate and inspect its preview.
3. Choose **Approve artwork** when satisfied.
4. Choose **Add or update in project → Add a separate copy** and keep or change
   the friendly name.
5. Select **Editor-visible cells (script-free scene)**, then **Prepare layout**.
6. Read the plan summary and confirm **Add this asset**.

Daydream detects Godot automatically. You should not need to type an executable
path or version. Preparation may take a few seconds and can ask permission to
use Godot; it does not run your game or add the layout until you confirm.

## Paint and save

Choose **How to open it in Godot** after adding the asset. Open the displayed
scene in Godot's FileSystem dock, then select its tile layer.

The placed cells should be visible **before pressing Play**. Paint or erase a
cell, save, close the scene and reopen it. Your edits should still be there.
Press **F6** to try this scene by itself.

Adding this scene does not replace the shop, level or main scene. Ask Daydream to
place it in the intended level as a separate step when you are ready.

## Keep manual edits safe

If you edit the imported scene in Godot, Daydream marks it as modified and won't
replace it through Update. Add a separate copy of a new candidate and compare
the two. There is no automatic merge of your painting into a new generated layout.

Before any update, save and close the scene in Godot. Daydream cannot detect
unsaved changes in an editor.

## What is the other layout option?

**Runtime layout companion (legacy)** is the older behavior: its placed tiles
appear when the scene runs. For a new layout you want to paint directly, choose
**Editor-visible cells**.

If you already added a runtime layout, add a separate editor-visible copy rather
than updating it in place. This keeps existing scene references and edits intact.

## Quick check

- Cells appear in the editor before Play.
- A painted cell and an erased cell survive save/reopen.
- Those edits also remain when running the scene.
- Adding a new copy leaves the original scene unchanged.

If any check fails, copy the error or take a screenshot and tell Daydream which
step failed. See [Troubleshooting](TROUBLESHOOTING.md).
