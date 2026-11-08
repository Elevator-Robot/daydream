# Feedback follow-ups — 2026-11-08

## Reported problem

The user received “Feedback already exists; it is retained rather than overwritten”
when adding another change request. The first note's immutable storage was correct,
but refusing all follow-up notes and suggesting an import copy was not a usable
feedback flow. No user artwork or saved feedback was modified to reproduce it.

## Fix

The first record remains byte-for-byte intact. Additional exact-revision notes are
separate immutable records, with content-derived identities. Identical reviewer/
text submissions are retained once. Shared status exposes all notes; validation,
permissions and change-request blocking apply to every record across sprite,
animation and tileset flows. Approval/import remain blocked until a new candidate.

The UI shows **Add more feedback** and **Read saved feedback** when notes exist.
Saving a note keeps the review open, preserving earlier notes and allowing further
clarification. Generic action errors no longer direct users to import a copy when
the failure has nothing to do with import.

## Validation

Commands completed:

```sh
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

**169 tests passed** with the optional environment and real Godot checks. The
dependency-free run passed with **70 optional tests skipped**. Tests cover all
asset types, original-byte preservation, read-only preview, exact read/write
grants, repeated notes, stale revision hashes, orphan notes, symlink/corrupt notes,
bounded histories, fresh revision state and continued approval/import refusal.

An actual standalone OpenCode TUI ran in an isolated synthetic project under
`/tmp/opencode/daydream-feedback-ui-*`, with temporary install/config/data/cache
destinations. It opened a candidate already containing “Make the outline darker,”
displayed **Add more feedback**, accepted “Also brighten the eyes” through the real
dialogs and permission prompt, and displayed saved feedback. Checks confirmed the
first record's bytes were unchanged, one follow-up was retained, and no approval
or import was created. The registered asset command was dispatched by the fixture's
TUI driver; this is not a claim of a human artwork review or real-game acceptance.

No actual user configuration, Potion Shop asset, external service or installed
dependency was changed. Temporary transcripts are machine-local, not durable
screenshots; the observations above are the retained verification record.
