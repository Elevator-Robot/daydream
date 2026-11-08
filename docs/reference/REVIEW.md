# Review and approval implementation reference

Contributor/integration reference. For everyday use, see [Your assets](../REVIEW.md).

The standard Daydream plugin now provides one integrated review flow for **static
sprites, animations and tilesets**. It does not require terminal approval commands
or a model call:

```text
/assets                         Your assets: current candidates, history and thumbnails
/assets art/slime-v1             Open a specific revision
```

The command palette entry is **Your assets**. `/assets` is the only asset-management
command; it has no legacy aliases. OpenCode's `/review` is code review. `/preview`
only views assets or runs/stops the game; it no longer routes to asset decisions.
Restart OpenCode if its TUI has not discovered the new command.
There is no new install flag, model-facing approval tool, service or browser server.

## The actual user flow

1. **Create:** describe a new asset to the session agent. Existing candidates let
   the user resume at their saved stage. Creation appears before candidate browsing;
   history, help and advanced path entry follow the normal workflow.
2. **Review/revise:** select a candidate and confirm opening its validated browser
   viewer. Inspect artwork, motion, layouts and collision geometry. Viewer startup
   alone does not establish review. The menu groups review actions before approval
   and adding/updating; Finish is last and Escape remains available.
   Drafts highlight **Open preview again**. Saving feedback retains the exact-revision
   note, blocks further approval/import of it and highlights **Make revised version**.
   That action submits the selected asset and all notes to the current session;
   saving a note alone does not start a model request. The result returns to review.
3. **Approve:** approval requires a reviewer label and explicit confirmation of the full
   revision hash and review responsibility. It records approval only—**no import**.
   Once approved, the menu highlights **Add or update in project** and marks the
   approval action completed. Highlighting does not dispatch an action.
4. **Add/update:** add a separate copy with
   automatically selected filenames, or explicitly update an unchanged registered
   asset at stable paths. Read the plain-language summary; exact paths/hashes are
   available under **Show technical details**. Apply is separately confirmed.
   [Guided assets](ASSET_LIFECYCLE.md) explains recovery snapshots and manual-edit protection.
5. **Preview:** the post-import menu highlights **Preview this scene**, still with
   separate launch confirmation and permissions. **How to open it in Godot** gives
   ordered manual steps, including placement guidance for new copies and game
   preview guidance for updates already referenced by gameplay.

Dialogs show the applicable stage out of five; success messages state the next
action. The browser shows the same ordered workflow with review as its current
stage. Finish/Cancel preserves already-confirmed decisions and saved notes.

Tilesets now offer a layout-mode choice: script-free **Editor-visible cells** or
the legacy runtime companion. Editor mode detects the project engine and checks
compatibility without asking for executable paths/version strings. Separate
isolated-serialization permission is still required before planning executes Godot.
It does not run the target game. Add-copy never overwrites; explicit managed
updates replace only verified unchanged outputs after backing them up. See
[editor-visible layouts](EDITOR_LAYOUTS.md).

If permissions deny a read, decision or write, that denial propagates; there is
no CLI fallback, auto-reply or permission widening. Cancel or Escape writes no
new decision/import. An approval already explicitly confirmed stays recorded if
the user later cancels import. Browser launch failure does not offer approval.
Errors/refusals now remain in an **Asset action stopped — details** dialog until
dismissed, rather than only appearing in a disappearing toast. Read/copy the exact
reason before retrying; no failed decision or import is automatically replayed.
Some system browser openers stay alive for the viewer's lifetime; Daydream checks
immediate errors but does not wait for browser exit or kill the viewer.

## Exact-revision and exact-plan safety

- Review tickets are server-generated, bound to the session, real project location,
  bundle, asset kind and revision hash. They expire after 20 minutes and are cleared
  on plugin unload. A moved session or changed/corrupt bundle requires a fresh review.
- Approval and feedback are written by the existing shared Python capability code,
  with scoped read/edit grants. Custom `daydream.review.approve` / `.changes`
  permissions include the exact bundle/hash and request no saved approval pattern.
  Existing user/agent permission rules still apply, including explicit allow/deny.
- `approval.json` remains compatible with CLI approvals. Feedback is an immutable
  `changes-requested.json` record with kind, hash, reviewer, UTC timestamp and note.
  Follow-ups use additional immutable `changes-requested.<digest>.json` records;
  the original record's bytes never change. The digest binds kind, revision hash,
  reviewer and note, allowing an identical submission to return `keep_feedback`
  without adding a duplicate. Status retains the original single-record fields
  and adds an ordered `feedback.notes` list. UI decisions offer **Add more feedback**
  and **Read saved feedback**; no note triggers generation or clears the change block.
- Shared feedback loading validates every recognized note before approval/import.
  Preparation enumerates note filenames without reading their contents, then
  requires exact read grants; a new follow-up needs its own exact write grant.
  Orphan follow-ups still prevent approval/import if the original record was
  removed outside Daydream. Symlinked, corrupt or wrong-revision notes fail closed.
  History is bounded to 32 notes / 256 KiB, with 4,000 characters per note.
  Managed feedback writes retain the existing per-bundle review lock.
- Status/feedback is discoverable via the read-only `review.inspect` operation.
  The model cannot decide approval
  through native tools. It must never call the decision RPC or CLI on the user's
  behalf without explicit human review/authorization.
- The user-interface RPC's `revise` action rechecks the ticket/session/project/hash
  and loads current feedback through permissioned `review.inspect`. It returns a
  request with the selected name, bundle, kind, hash and complete notes, without
  writes. Only the explicit **Make revised version** click calls the documented
  `context.client.session.prompt({ sessionID, text })`; the normal agent loop does
  the editing with its existing tools/permissions. The TUI checks the active
  session again after preparing the request, closes review after admission, and
  reports submission failure without retry. The per-command busy guard prevents
  repeated dispatch during submission. An uncertain transport failure asks the
  user to check chat before resending; this is not a durable generation job or an
  exactly-once guarantee across clients. No name/path entry or separate chat prompt
  is needed. The request requires fresh revision storage, preserved history and
  preview before a new user approval/import decision.
- Import plans include the exact revision, generated output content/paths and
  resulting asset-index content. The shared backend rechecks `revision_hash` and
  `plan_hash` before writes. A stale plan is refused, even when destinations happen
  to remain the same. A new plan must be shown and explicitly confirmed.
- A per-bundle `.review.lock` serializes managed approval, feedback and import writes;
  imports also retain the existing project-level lock, sidecar/collision refusal,
  concurrent metadata checks and non-overwriting new imports. Explicit managed
  updates additionally require unchanged file hashes and recovery snapshots. Lock/temp files are
  implementation details of the permissioned logical output.
- Cancellation/failure during writes may leave partial new output. Inspect it before
  retrying; there is no destructive rollback, automatic retry or stale-lock deletion.

This is a **workflow and permission boundary, not an OS sandbox or authenticated
human identity system**. Reviewer labels are self-declared. The user-interface RPC
is not exposed as a model-facing decision tool, but arbitrary local code or another
authorized OpenCode API client is not cryptographically prevented from using it.
The documented CLI remains available for explicit human-authorized fallback work.

## What did not change

Preview does not approve. Approval does not import. Adding a copy does not place assets
in existing game scenes, playtest the game, approve future revisions, or authorize
unrelated changes. Updating a managed asset does affect scenes already referencing
its stable resource paths. Art/motion/terrain/collision quality still requires human judgment.
Changing pixel data, animation timing, tile layout or collision flags needs a new
revision and fresh review. No general image provider, editor control, dependency
installation or game-engine upgrade is added.

## Verification

The Python suite tests shared state, hash-bound immutable feedback, all three asset
kinds, denial of model-facing decisions, scoped UI grants, stale imports, locks and
symlink refusal. Node tests exercise service tickets, expiry/session binding,
permissions, cancellation, UI decisions and separate import confirmation using the
real Python backend in isolated synthetic projects.

An actual standalone OpenCode TUI was driven through approval, separate import,
animation change requests and tileset cancellation with temporary configuration
and a synthetic project. The browser was opened by the real client-side opener.
See [the dated validation record](../validation/2026-11-05-asset-review.md). None of
these fixture approvals represents approval of user artwork or an existing game.
