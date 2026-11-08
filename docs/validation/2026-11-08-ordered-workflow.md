# Ordered workflow guidance — 2026-11-08

## User direction

The user requested that Daydream consistently guide the flow and present steps
in order of operation. This is now a standing requirement in contributor
`AGENTS.md` and the installable `agents/daydream.md`, rather than advice limited
to one conversation.

## Applied changes

The asset UI, browser preview and user walkthrough now share five stages:

1. Create.
2. Review or revise; revised candidates return to this stage.
3. Approve.
4. Add or update after reviewing the plan.
5. Preview the result.

Menus use ordered categories and stage labels. Creation precedes candidate
browsing, with history/help/advanced choices afterwards. Draft review highlights
viewing; saved feedback highlights revision; approval highlights add/update; a
successful import highlights scene preview. Highlighting never executes an action.
Finish remains available, and existing confirmation/permission boundaries remain.

Toasts describe the next action. Manual Godot guidance lists opening, inspecting,
standalone playtesting and game-context placement/testing in order. Normal labels
and selected asset context are retained. No new approval screens or slash commands
were introduced. The ordered browser strip highlights review as the current stage.

## Validation

Required suite commands:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The full optional run passed **all 169 tests**, including isolated Godot checks.
The dependency-free run passed with **70 optional tests skipped**.
`git diff --check` passed. Existing behavioral tests were reused for this
presentation/guidance change.

An actual standalone OpenCode TUI used a synthetic project and temporary
install/config/data/cache under `/tmp/opencode/daydream-guidance-ui-*`. The fixture
dispatched the registered asset command; subsequent choices used keyboard input
through the real dialogs. It verified:

1. Creation and candidate-review categories appear in operation order.
2. Selecting the synthetic candidate opens the step-2 preview/review guidance.
3. Approval follows review, including the step-3 exact confirmation and actual
   permission prompt; only the synthetic candidate receives an approval record.
4. The next highlighted action opens step 4. Copy/name/plan choices and a separate
   apply confirmation create the synthetic scene.
5. Step 5 offers scene preview; Escape finishes without launching a game.

The browser fixture from the comparison work was rerendered in isolated Chromium.
Its real DOM contains the five ordered stages and marks review as current. The
desktop screenshot was opened and visually inspected: the compact stage strip is
readable above the comparison controls. Comparison selection, shared zoom, narrow
layout and motion replay checks still pass. No model request or user-game change
was needed for these checks. Temporary transcripts/captures are machine-local;
this is not human approval of real artwork or user branch acceptance.
