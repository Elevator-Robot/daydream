# Preview RPC JSON response fix — 2026-11-08

## Report and cause

The user received `Daydream preview: Expected JSON value at ["code"]` from an
existing Godot project. The shared preview snapshot returned own properties with
`undefined` values for a running process's not-yet-known exit code and signal.
OpenCode validates RPC output as JSON values before serialization and rejects those
properties. The native adapter's `JSON.stringify` silently omitted them, and the
earlier in-process tests did not exercise that transport distinction.

The game could have launched successfully before the RPC response failed. This
does not imply malformed project JSON or a Godot crash.

## Fix

Shared snapshots now omit only undefined fields. Real zero exit codes, explicit
null codes on signal termination, diagnostics, state and evidence remain intact.
The TUI shows numeric exit codes and termination signals, avoiding an `Exit: null`
display. Launch permissions, engine selection, duplicate detection and owned-process
cleanup are unchanged.

## Regression checks

The revised running/exit tests failed before the fix, exposing `code: undefined`
and `signal: undefined`. They pass afterwards. Checks cover initial launch, running
status, duplicate launch responses, signal termination, successful zero exit and
nonzero exit. Each response must equal its JSON round trip without losing fields.

```sh
node --test --test-name-pattern='game launches graphical|immediate exits' tests/preview.test.mjs
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The two targeted regressions passed after the fix. The full optional run passed
**all 169 tests**, including Node and isolated Godot checks. The dependency-free
run passed with **70 optional tests skipped**. `git diff --check` passed and
**156 local documentation links** resolved.

## Actual RPC check

A standalone OpenCode TUI with temporary install/config/data/cache used a synthetic
Godot project under `/tmp/opencode/daydream-preview-rpc-*`. Its fixture driver called
the actual `daydream.preview` RPC through the documented client, not directly into
the JavaScript service. Fixture-scoped permissions allowed only the intended test
workflow; no actual user configuration was changed.

With Godot `4.7.2.stable.arch_linux.ed1daf0bf`, the RPC successfully returned:

1. Initial `not_running` status.
2. `running` after graphical launch, with no exit code/signal properties.
3. `running` status for the same process.
4. `already_running: true` and the same PID on repeated launch.
5. `stopped` after stopping only the owned fixture process.
6. `exited`, `code: null`, `signal: "SIGTERM"` after stopping.

This verifies real RPC validation and real Godot process lifecycle, not artistic
correctness or play feel. The user's existing game, editor and game files were not
modified or used as a test fixture. Temporary result JSON and terminal transcripts
are machine-local evidence.
