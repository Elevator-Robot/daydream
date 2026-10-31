# Daydream laser intro

An optional **OpenCode V2 TUI plugin** displays a non-modal text-art intro above
the session composer. A cyan laser sweeps across a violet block-letter
`DAYDREAM` wordmark, etching the letters into place with small sparks. The finished
art holds briefly, then disappears. Total duration: **2.4 seconds**, at no more
than 20 updates per second. It does not flash or loop.

The effect is inspired by Omarchy's terminal screensaver aesthetic, but uses
original artwork and a small in-process renderer. No Omarchy, `ttfx`, external
font, child process, or background service is required. It does not modify your
screensaver, terminal settings, or desktop configuration.

## Opt-in installation

From your permanent Daydream checkout:

```sh
python3 scripts/install.py --with-intro          # preview both links
python3 scripts/install.py --with-intro --apply  # opt in
```

In addition to the normal agent link, this links
`~/.config/opencode/plugins/daydream-intro` to this checkout's
`plugins/daydream-intro` directory. Use `--config-dir` for a nonstandard OpenCode
configuration directory. Both requested destinations are checked before writes;
existing conflicting paths are never overwritten. Rerunning is safe. As with
agent installation, an I/O error or concurrent change can leave a partial install:
inspect the result and rerun after resolving the error.

The installer does **not** edit `opencode.json`, `cli.json`, game projects, or
model/permission settings, install npm packages, or enable the plugin itself in
the running client. Restart OpenCode after opting in. OpenCode discovers the
plugin directory and supplies its UI runtime imports.

Running the installer without `--with-intro` still requests **only the agent**;
it does not remove an intro installed previously.

## When it plays

- Automatically once per visible **primary Daydream session** per TUI process,
  after a session exists and its saved `agent` is `daydream`.
- Opening another Daydream session plays that session's intro. Returning to an
  already-seen session does not replay it. Memory survives plugin hot reloads;
  restarting the TUI resets it.
- Selecting an agent on the home screen before a session exists is not detectable
  through the public selected-agent UI API verified for OpenCode 2.0.32. The intro
  therefore appears when the Daydream session composer mounts, not at that earlier
  selection. It does not run for unrelated agents, background sessions, or
  subagents. An `@daydream` mention alone does not switch the active primary agent.
- `/daydream-intro` replays it in a primary Daydream session;
  `/daydream-hide-intro` dismisses it. Both also appear in the command palette.
- Small terminals get a compact wordmark; extremely small terminals suppress the
  intro. The animation never grabs input, opens a modal, replaces a permission
  prompt, or delays agent work.

Switching away, unmounting the composer, dismissing, or unloading the plugin
cancels scheduled animation work. No terminal escape sequences are printed:
OpenTUI owns rendering, terminal restoration, and normal input handling.

## Reduced motion and disabling

For advanced configuration, load the local plugin through the documented
OpenCode plugin options. Use **one** installation route: do not also symlink the
same plugin through the installer. For a TUI-only plugin, merge an entry into your
existing global `cli.json` without replacing other settings:

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

`reducedMotion: true` shows only the completed art for 2.4 seconds, without an
animation loop. `enabled: false` disables the plugin's UI and commands. These are
plugin options, not `.daydream/config.json` fields; no new project metadata is
needed for a purely client-local visual.

To uninstall the symlink route, inspect the installed plugin symlink and remove
**only that symlink**. Keep the agent link if desired. For the explicit config
route, remove only its plugin entry. Restart OpenCode after changing installation.

## Validation and compatibility

The public TUI plugin interfaces, session `agent`/`parentID` fields, slot, and
runtime imports were checked against OpenCode V2 documentation and the published
2.0.32 package declarations. The implementation uses the supported
`session.composer.top` slot, in-memory plugin storage, and Solid lifecycle cleanup.
It does not register server workflow hooks or change model prompts/history.

Run the dependency-free animation tests with **Node.js 18+**:

```sh
node --test tests/intro.test.mjs
```

The Python suite runs these and the plugin's JavaScript syntax check when Node is
available, otherwise it skips those checks. Python helpers still have no new
dependencies. Tests cover final artwork, bounds, agent/session scope, timing,
reduced motion, cancellation, and stale callbacks. Installer tests use temporary
config directories only.

**Not yet verified:** live plugin loading and graphical appearance in the target
OpenCode TUI. Syntax and pure lifecycle tests are not a graphical integration
test. After installing, manually check:

1. Start/open a primary Daydream session; confirm the cyan sweep and final art.
2. Type during the intro; check input remains usable and permission UI is intact.
3. Return to the session, switch agents, and open an unrelated session; verify no
   unwanted repeats or background animations.
4. Replay, dismiss, resize, and try reduced motion in light/dark themes.
5. Disable/unload during playback; verify no remaining timers or stale UI.

References: [TUI plugin API](https://opencode.ai/v2/docs/build/plugins/cli),
[plugin discovery/options](https://opencode.ai/v2/docs/cli/plugins), and
[agent selection](https://opencode.ai/v2/docs/agents).
