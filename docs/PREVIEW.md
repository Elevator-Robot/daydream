# Preview your game and artwork

Use **`/preview game`** to playtest. Use **`/assets`** to manage artwork.

| Command | What it does |
| --- | --- |
| `/preview` | Offers Game, Asset, Status and Stop |
| `/preview game` | Runs your project's normal starting scene in Godot |
| `/preview asset` | Opens an artwork preview without approving or adding it |
| `/preview status` | Shows whether the preview is running and recent messages |
| `/preview stop` | Stops the game preview Daydream started |

Open these commands while you have a project session open. You can also find
**Preview game or asset** in OpenCode's command palette.

## Play the game

1. Open the intended game project in Daydream.
2. Run `/preview game` and confirm the launch.
3. Play in the Godot window and test the behavior you changed.
4. Use `/preview status` if it fails or behaves unexpectedly.
5. Use `/preview stop` when finished.

Starting a game runs its code and can write imports or saved data, so only launch
projects you trust. Daydream uses your project's configured Godot or the installed
Godot it can find. Keep the engine version your game expects.

If a preview is already running, Daydream doesn't launch another identical copy.
Stop it before switching to a different scene. Stop does not close an editor or
game instance you started yourself.

## Try only the new asset scene

After adding or updating an asset through `/assets`, choose **Preview this scene**.
This runs the new standalone scene without changing the game's normal starting
scene. It still runs project code, and requires launch confirmation.

You can also open the saved scene in Godot and press **F6**. Press **F5** to run
the project's normal starting scene.

## Inspect artwork without playing

Run `/preview asset`, select a candidate and confirm opening the browser.
Use **Artwork scale** to inspect pixels. **Compare with previous version** shows
the selected candidate beside an earlier version, with their saved feedback.
The **Older version** picker changes the reference side; your selected candidate
stays fixed. Large images scroll, and narrow screens stack the two versions.

Watch animation playback rather than judging it only from a still image. Clips
use their own timing; **Replay motion** restarts both visible versions. For tiles,
inspect the layout and collision outlines. Numbered tiles and animation contact
sheets remain available in expandable details.

Viewing is not approval. When you are ready to approve, request changes or add the
asset to the project, return to **`/assets`**.

## If nothing opens

- Run `/preview status` and copy any error.
- If the main scene is missing, choose the starting scene in Godot first.
- If Godot cannot be found or its version is wrong, ask Daydream to check your
  project's setup. Don't upgrade the game just to dismiss an error.
- If OpenCode is running on another machine, the game window opens there. For
  local playtesting, run OpenCode and Godot on your desktop machine.

More help: [Troubleshooting](TROUBLESHOOTING.md).
