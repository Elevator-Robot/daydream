# Discoverable asset operations

Daydream's local capability catalog is shared by the CLI and the included native
OpenCode V2 server plugin. It reuses the existing sprite rendering, revision,
approval and import implementations. No MCP server, daemon, cloud account,
generation provider, or permission changes are added.

## CLI

From a game directory, using the checkout's launcher or installed `daydream`:

```sh
daydream ops search animation
daydream ops describe animation.assemble
daydream ops call animation.assemble --input-file assemble.json
# After reviewing the non-writing plan:
daydream ops call animation.assemble --input-file assemble.json --apply
```

`daydream ops --project /path/to/game ...` selects the CLI workspace explicitly.
Paths must remain inside it, with no traversal, sensitive configuration paths,
or symlink components. Existing helper CLIs remain compatible.

CLI writes require `--apply`; an input JSON `apply:true` alone is rejected.
Use the optional sprite interpreter when the launcher's Python lacks Pillow:

```sh
/path/to/daydream/.venv-sprites/bin/python /path/to/daydream/scripts/operations.py \
  --project /path/to/game search animation
```

The catalog includes `project.init`, `sprite.create/from_png/edit/inspect/approve/import`
and `animation.create/assemble/edit/inspect/approve/import` (each slash-separated
action is its own `area.action` ID). Describe returns exact bounded input schemas.
Environment art adds `tileset.create/transitions/edit/inspect/approve/import`;
see [tilesets](TILESETS.md) for terrain, seams, collisions and approval boundaries.
`animation.assemble` takes existing static revision bundles, ordered frame IDs,
named clips, durations, loop flags and a shared pivot; it validates canvas and
palette consistency and generates standard animation artifacts/provenance.

## Native tools included in the standard install

The standard installer includes the whole-directory native plugin link. Existing
installations can use the same commands to add missing components safely:

```sh
python3 scripts/install.py
python3 scripts/install.py --apply
```

This does not install Pillow, change permissions, or edit OpenCode config JSON.
Keep the checkout in place. Restart OpenCode to discover the plugin.
`--agent-only` explicitly omits all plugins and the launcher; it does not remove
components already installed. Tool availability does not imply Pillow is installed.
The plugin uses `.venv-sprites/bin/python` if executable, otherwise `python3`;
an explicit trusted plugin `options.python` can select another interpreter.

`daydream_search`, `daydream_describe`, and `daydream_call` expose discovery and
execution. Common sprite/animation actions also have direct names derived from
the catalog, such as `daydream_sprite_create` and `daydream_animation_assemble`.
`project.init` and PNG ingestion are available through the generic caller.
The session's actual location chooses the workspace, not a model-supplied path.

The adapter prepares exact read resources, asserts OpenCode `read` permission,
executes a real non-writing preview, and asserts `edit` permission over planned
output resources before apply. Adapter-owned grants constrain shared-core file
reads/writes during execution, including a changed import destination. Permission
rejections propagate; there is no shell fallback or automatic allow rule.
Directory creation, exclusive locks and temporary manifest replacement are
implementation details of the authorized logical output, not separate assets.
These checks are not an OS sandbox or protection against malicious local code.

## Outcomes and review

Results contain `ok`, `status`, operation ID, structured results/artifact paths,
access plans, and explicit evidence limits. States are `preview`, `done`,
`needs_approval`, or `error` (`prepared` is adapter-only). Coded errors include
missing dependencies, conflicts, invalid input, scope violations and cancellation.
Artifacts returned by a preview are planned paths, not written images.

Neither successful tool execution nor inspecting a contact sheet establishes
motion quality or graphical Godot correctness. Model-facing tools **cannot write
approval decisions**. The user can now use `/asset-review` for exact-revision
approval or change requests, with a separately confirmed import plan; the CLI
approval remains an explicitly authorized fallback. See [review](REVIEW.md).
Reviewer labels are not authenticated proof of human identity.

`review.inspect` is a read-only catalog operation for approval/feedback state.
`review.feedback` is user-UI/authorized-CLI only. A changes-requested record blocks
further approval and import of its exact revision until a fresh revision is made.
Imports optionally accept `revision_hash` and `plan_hash` to refuse a changed
candidate, destinations, generated content or asset index before writing.

Cancellation/unload terminates backend work; the runner imposes a 120-second
limit and 1 MiB request/result limits. Cancellation or failure during writes can
leave partial new files. Inspect before retrying; never automatically retry writes
or overwrite a partial candidate. Collision refusal is not durable idempotency.

## Validation boundary

Python tests exercise CLI preview/apply, schema validation, scope refusal,
adapter-grant enforcement, frame assembly, exact approval, and import in isolated
fixtures. Node tests check canonical-schema parity, permission ordering/denial,
session location and pre-cancellation. Installed-symlink checkout resolution is
regression-tested. Live OpenCode loading and `daydream_describe` execution were
verified after fixing symlink-relative backend discovery. Live asset write/
permission flows and human visual/motion acceptance remain unverified.

Architecture evidence and rationale: [pinned Summer study](research/SUMMER_ARCHITECTURE.md).
