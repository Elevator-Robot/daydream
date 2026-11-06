# User review, approval and import

The standard Daydream plugin now provides one integrated review flow for **static
sprites, animations and tilesets**. It does not require terminal approval commands
or a model call:

```text
/asset-review                    Pick a staged asset revision
/asset-review art/slime-v1       Review a specific revision
/preview review                 Same flow through the preview picker
```

The command palette entry is **Review and approve an asset**; `/daydream-review`
is an alias. OpenCode already uses `/review` for code review, so Daydream leaves
that command alone. Restart OpenCode if its TUI has not discovered the new command.
There is no new install flag, model-facing approval tool, service or browser server.

## The actual user flow

1. Select a bundle or enter a project-local path; confirm opening its browser viewer.
   The shared inspector verifies the files and exact manifest hash. The dialog
   shows the candidate name, review state and hash prefix; the full hash appears
   in the browser and final confirmation.
2. Inspect the actual sprite, watch animation motion, or check tile layout and
   collision outlines and exact geometry/settings. Viewer startup alone does not establish review.
3. Choose **Approve exact revision**, **Request changes**, or **Cancel**. Cancel
   is the default selection. Reopening the same preview is also available.
4. Approval requires a reviewer label and an explicit confirmation of the full
   revision hash and review responsibility. It records approval only—**no import**.
5. Request changes requires feedback, a reviewer label and confirmation. The note
   is retained against that exact revision; further approval/import of it is blocked.
   Create a fresh revision to address the feedback. No generation/model request is
   started automatically, and assets already imported are not removed.
6. Once approved, choose **Review import plan**, using project defaults or explicit
   name/destination overrides. Read the complete create/update path list and plan
   hash, then separately confirm **Apply import**, or leave the asset staged.

If permissions deny a read, decision or write, that denial propagates; there is
no CLI fallback, auto-reply or permission widening. Cancel or Escape writes no
new decision/import. An approval already explicitly confirmed stays recorded if
the user later cancels import. Browser launch failure does not offer approval.
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
  Repeat identical feedback is harmless; different feedback does not overwrite it.
- Status/feedback is discoverable via the read-only `review.inspect` operation.
  Ask Daydream to address the saved feedback; the model cannot decide approval
  through native tools. It must never call the decision RPC or CLI on the user's
  behalf without explicit human review/authorization.
- Import plans include the exact revision, generated output content/paths and
  resulting asset-index content. The shared backend rechecks `revision_hash` and
  `plan_hash` before writes. A stale plan is refused, even when destinations happen
  to remain the same. A new plan must be shown and explicitly confirmed.
- A per-bundle `.review.lock` serializes managed approval, feedback and import writes;
  imports also retain the existing project-level lock, sidecar/collision refusal,
  concurrent metadata checks and non-overwriting behavior. Lock/temp files are
  implementation details of the permissioned logical output.
- Cancellation/failure during writes may leave partial new output. Inspect it before
  retrying; there is no destructive rollback, automatic retry or stale-lock deletion.

This is a **workflow and permission boundary, not an OS sandbox or authenticated
human identity system**. Reviewer labels are self-declared. The user-interface RPC
is not exposed as a model-facing decision tool, but arbitrary local code or another
authorized OpenCode API client is not cryptographically prevented from using it.
The documented CLI remains available for explicit human-authorized fallback work.

## What did not change

Preview does not approve. Approval does not import. Import does not place assets
in existing game scenes, playtest the game, approve future revisions, or authorize
unrelated changes. Art/motion/terrain/collision quality still requires human judgment.
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
See [the dated validation record](validation/2026-11-05-asset-review.md). None of
these fixture approvals represents approval of user artwork or an existing game.
