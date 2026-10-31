# Daydream intro — Omarchy's actual laser effect

The optional OpenCode V2 TUI plugin runs **`ttfx laseretch`**, the same terminal
effects engine Omarchy's screensaver uses. This is not a JavaScript approximation
of the laser. The earlier custom sweep has been removed.

Omarchy selects random effects from `ttfx`. Daydream selects `laseretch`
explicitly, at the same **120 FPS setting**, preserving its real diagonal beam,
flying sparks, hot-character cooling, and gradient animation. The foreground
colors are now deliberately customized with documented `ttfx` gradient options:
neon cyan, hot magenta, electric violet, and amber/white highlights. The plugin
preserves the resulting emitted RGB colors and character positions.
Frames are written with native `StyledText` chunks containing explicit RGBA
foregrounds, rather than relying on reactive nested span styling. A terminal
capture verified the rendered word has distinct magenta/violet/cyan RGB values;
playback acknowledgement alone is not used as evidence of correct color.

Daydream's retro-cyberpunk typography uses only a readable, upright block
wordmark with no diagonal cuts or shear: no text above or below it. Narrow
layouts use a letter-spaced wordmark
instead of compressing or clipping the large lettering.
Reduced-motion artwork uses the same cyan/magenta/violet foreground gradient.
This is text-art typography, not a terminal font installation or a change to
OpenCode's surrounding UI font. The artwork is original Daydream branding.

## Integration and dependency

- Requires an existing **`ttfx` executable on the TUI client's PATH**. This was
  tested with the installed `ttfx 0.5.0`. Nothing downloads or installs it.
- Starts one bounded child process with a fixed argument list and `shell: false`.
  Original artwork is sent over stdin; no temporary files or game assets.
- Captures stdout, decodes complete truecolor canvas frames, and draws those
  frames in OpenCode's `session.composer.top` slot. **No background is painted**:
  boxes, text, and spans inherit the existing OpenCode background, including any
  transparency supplied by the host. ANSI background/terminal-background controls
  are ignored rather than forwarded. No black rectangle or global theme override.
- Cursor controls are consumed by the decoder, **never written to the terminal**.
  OpenTUI keeps ownership of input, terminal restoration, and permission dialogs.
- A bounded, centered intro canvas replaces the screensaver's fullscreen canvas.
  Small terminals use `DAYDREAM` text without resizing the glyphs. Very small
  terminals suppress the UI. The animation itself is still the real effect.
- Plays to completion, holds the last frame for 350 ms, then breaks the wordmark
  into colored particles which scatter and dissipate over about 660 ms. This short
  bounded outro is local particle animation, not a claim that `ttfx laseretch`
  provides an explosion phase. Reduced-motion mode has no explosion. A 30-second
  watchdog terminates abnormal runs; it is not forced into the previous 2.4-second
  imitation. Canvas dimensions and buffered output are bounded too.
- Dismissal, agent/route changes, resize, unmount, or unload stop the owned child.
  Termination escalates to SIGKILL after 500 ms if necessary. No `pkill`, unrelated
  process termination, screensaver launch, desktop changes, or background daemon.
- Missing/incompatible `ttfx`, unsupported output, or timeout produces a warning.
  There is **no imitation fallback** and no automatic software installation.

This is a concrete local-process integration, not a server workflow hook. The
standard Python helpers and agent-only installation retain their existing
dependencies and behavior.

## Opt-in installation

From your permanent Daydream checkout:

```sh
python3 scripts/install.py --with-intro          # preview both links
python3 scripts/install.py --with-intro --apply  # opt in
```

Besides the agent link, this links
`~/.config/opencode/plugins/daydream-intro` to the checkout's
`plugins/daydream-intro` directory. Use `--config-dir` for a nonstandard OpenCode
config directory. Existing conflicting paths are never overwritten; requested
links are preflighted before writes. An I/O error or concurrent change can still
leave a partial install: inspect the result before retrying.

The installer does not edit `opencode.json`, `cli.json`, game files, models, or
permissions, or install `ttfx`/npm packages. Restart OpenCode after installing or
updating. Keep the checkout in place. The default installer remains agent-only;
running it without `--with-intro` does not remove a previously installed plugin.

## When it plays

- **To enter without sending a message:** choose **Open Daydream** in the command
  palette, or run the client-side `/daydream` action. It creates an empty primary
  Daydream session in the current location, syncs its data, and opens it. The intro
  starts on entry, before any prompt, model request, tool run, or game-file write.
  Your currently selected model/variant is carried into the new session without
  changing defaults. Each deliberate activation opens a new session; duplicate
  concurrent activations are ignored. Errors are surfaced, and a failed sync can
  retry the same empty session rather than creating duplicates.
- **Explicit-only:** `/agent`, the built-in agent selector, agent cycling,
  `@daydream` invocation, session restoration, and ordinary messages do not request
  or trigger art. Opening an existing session or restarting OpenCode does not
  replay it either. There is no automatic selected-agent/session-mount trigger.
- **Open Daydream** sends a one-shot client-local intro request after opening its
  empty primary session. The request is consumed once; returning to that session
  or switching agents cannot reuse it. No persisted startup flags are written.
  Background sessions, unrelated agents, and subagents cannot display the art.
- `/daydream-intro` replays it; `/daydream-hide-intro` dismisses it. Both are in
  the command palette. There is no input grab, modal, or delay to model work.

## Reduced motion and disabling

For explicit plugin options, use one installation route rather than loading the
same plugin both through discovery and configuration. For the config route, merge
an entry into the existing global `cli.json` without replacing other settings:

```json
{
  "plugins": [
    {
      "package": "/absolute/daydream/plugins/daydream-intro",
      "options": { "reducedMotion": true }
    }
  ]
}
```

`reducedMotion: true` displays static artwork for 2.4 seconds and starts no child.
`enabled: false` disables the plugin's UI and commands. Neither is a project-local
`.daydream/config.json` field. If moving from the installer to explicit options,
inspect and remove only the installed plugin symlink first.

To uninstall, remove only the confirmed plugin symlink or its explicit config
entry, then restart OpenCode. The agent link may remain.

## Validation and remaining visual review

The TUI interfaces, session fields, slot, and UI imports were checked against
OpenCode V2 documentation and published 2.0.32 declarations. Captured output from
the installed `ttfx` established the decoder's canvas framing and truecolor
format. Automated tests exercise the real engine as well as synthetic cases:

```sh
# Node.js 18+: parser, scope, process arguments, errors, cancellation, reduced motion.
node --test tests/intro.test.mjs
node --test tests/open-daydream.test.mjs

# Opt into the installed engine; nothing is downloaded.
TTFX_BIN=/usr/bin/ttfx node --test tests/intro.test.mjs
```

The Python suite runs the dependency-free Node tests and JavaScript syntax check
when Node is available, otherwise it skips them. Installer tests write only to
temporary config directories. The real-engine test verifies decoded frames,
emitted colors, and final text; it does not establish live TUI appearance.

The home-screen entry was also exercised in the installed OpenCode 2.0.32 TUI
through a real pseudo-terminal: open the command palette, select **Open Daydream**,
and capture the resulting laser frames without submitting a chat message. This
reproduced and fixed a command-scope bug: the keymap layer must use `mode: "global"`
to be reachable while the home prompt owns input. A unit regression test now
asserts that scope. This validates runtime entry and rendering output, not a
human visual judgment of the effect or every terminal/font combination.

**Human visual review remains pending.** After restarting OpenCode:

1. Choose **Open Daydream** from the home-screen command palette, without sending
   a message. Verify the new empty session opens and the intro begins. Replay
   it if needed. Compare its beam, sparks,
   cooling, and gradient with the actual `ttfx laseretch` engine, not the old
   custom sweep; expect Daydream's intentional cyberpunk palette rather than the
   screensaver's default palette. Check the existing background shows through.
2. Confirm the wordmark is not clipped and normal typing/permission UI still work.
3. Switch agents/routes, resize, dismiss, and unload during playback. Confirm the
   child exits and unrelated sessions do not trigger the intro.
4. Try reduced motion and a missing dependency; verify static mode and the warning
   respectively, without an animation substitute or software download.

References: [OpenCode TUI API](https://opencode.ai/v2/docs/build/plugins/cli),
[plugin discovery/options](https://opencode.ai/v2/docs/cli/plugins), and the local
read-only `/usr/share/omarchy/bin/omarchy-screensaver` and `ttfx laseretch --help`.
