# Asset lifecycle implementation reference

Contributor/integration reference. For everyday use, see [asset history and updates](../ASSET_LIFECYCLE.md).

Start with a normal request—“Create a tile named **Potion Shop Floor**”—then use
**`/assets`**. Daydream handles file-safe IDs and revision locations. You review the
artwork, explicitly approve it, and separately choose what should happen in the game.

`/assets [revision-folder]` is the only asset-management command, titled **Your
assets** in the command palette. The former asset-review shortcuts are removed,
not preserved as aliases. `/preview` is for viewing/playtesting and OpenCode's
`/review` remains code review. Creating, approving and applying assets lives in `/assets`.

## The everyday flow

1. Ask Daydream to create/revise an asset, or choose **Describe a new asset…** in
   `/assets`. That explicit action sends your brief to the current agent/model;
   browsing/reviewing alone does not invoke a model. Names may contain
   spaces, capitals, accents or punctuation. The human label is retained; a bounded
   file-safe ID is derived automatically. These are asset labels, not destination paths.
2. Open `/assets`. The picker shows the newest candidate per kind/ID, friendly names,
   status and an older-revision count. Choose **Show older revisions**, **View imported
   assets**, or **Open thumbnail overview** when useful. Overview validates up to
   12 current candidates; animation thumbnails do not count as motion review.
3. Choose a candidate, open its preview, then approve or request changes. Approval
   still refers to exact bytes, not every future version bearing that name.
4. Choose **Add or update in project**:
   - **Add a separate copy** chooses available filenames automatically. Keep the
     friendly name or give another; no `v1/v2` naming convention is required.
   - **Update [asset]** keeps a registered asset's current paths/references. It is
     disabled when disk edits or missing files are detected, or the exact revision
     is already imported. Use a separate copy to preserve manual changes.
5. Read the plain-language summary. Paths, hashes and recovery locations are under
   **Show technical details**. Apply/Add is a separate explicit confirmation.
6. The result offers instructions for opening the scene in Godot or **Preview this
   scene**. Scene preview requires normal run permission and executes project code;
   it does not rewrite the project's main scene.

If tracking metadata is missing, the UI offers **Set up asset tracking**, preserving
existing files. New imports default to configured asset/source roots. Tilesets offer
editor-visible versus legacy runtime layout for new copies; updates retain the
existing file layout. Engine discovery stays automatic for editor-visible mode.

Plan errors stay readable and return to the review choices rather than discarding
the review. No operation is silently retried, self-approved or upgraded to force
an overwrite. Legitimate refusals still exist—corruption, denied permission,
stale plans, incompatible resource identities or concurrent edits must not be hidden.

## Clean revision storage

The native/operation create and edit schemas now make `output` optional. Without it,
new immutable candidate bundles go under:

```text
.daydream/revisions/<kind>/<asset-id>/<manifest-hash>-<sequence>/
```

The shared implementation picks the next unused location without overwriting any
revision, and returns the exact review path. Human labels are retained in provenance.
The picker collapses history by default; previous candidates remain recoverable via
**Show older revisions**. Artwork, timing, layout, collisions or feedback still need
their normal exact-revision review. Explicit output paths and old helper CLIs remain
available for advanced/fallback use.

This applies to **new** tool-created candidates. Existing `art/.../v1/v2` bundles
are not moved/deleted/migrated automatically. Nothing is pruned automatically, and
history still uses disk space. Hidden storage keeps the dev workspace tidy; it is
not a replacement for version control or a promise that history is ignored by Git.

## Stable-path managed updates

`strategy: "update"` targets an exact registered asset ID. It requires fresh
approval of the selected revision, plus the exact `plan_hash` for apply. The store:

1. Validates the registered kind, paths and hashes. Every managed output must still
   match its recorded bytes. Missing or manually edited files refuse the update.
2. Requires the same file layout. Runtime-to-editor layout conversion, relocation
   or changing resource type needs a separate copy, not implicit file deletion.
3. For tilesets, preserves existing tile IDs/order, atlas columns, tile size and
   terrain numbering so existing cells do not silently refer to different tiles.
4. Plans the replacement files, index change and complete recovery snapshot. Exact
   output bytes, prior index and resulting index are part of the plan hash.
5. Acquires the existing project/bundle locks, rechecks current bytes, and saves
   the old managed files and metadata **before replacing any output**.
6. Replaces only those managed files, checking again immediately before each
   replacement, then updates the asset index. Godot `.import`/`.uid` sidecars and
   unrelated registry annotations are left intact.

Old imported bytes and the prior record are stored under:

```text
.daydream/history/imports/<asset-id>/<plan-hash>/
  files/<original project-relative paths>
  asset-record.json
  assets-before.json
  plan.json
  applied.json          # Written only after file/index application finishes
  .gdignore
```

An update changes resources already referenced by scenes; **Add a copy** does not.
Save and close editors working on those files before updating: disk hashes cannot
detect unsaved editor buffers. Checks/locks detect managed-operation conflicts and
observed disk changes, not arbitrary hostile local writers or uncooperative editor
races. There is no multi-file filesystem transaction or live-engine hot-reload guarantee.

Interruption can leave partially updated output. The prior snapshot remains, and
hash mismatch or an existing recovery snapshot blocks a blind retry. Nothing is
automatically rolled back, deleted or force-replaced. Inspect the recorded plan and
backup before recovery; do not restore the entire old index over unrelated newer work.
`applied.json` absence means completion is not confirmed, not proof that no files changed.

To return to an older retained candidate, select it from history and review an
explicit Update plan against the current unchanged managed asset. Manual edits
still require a separate copy. Snapshots retain imported bytes even if the original
candidate was later removed, but there is no automatic snapshot-restore/prune tool
in this slice; that recovery needs deliberate file-by-file reconciliation.

## Tools and evidence

- `assets.list` / `daydream_assets_list`: current candidates and imported/manual-edit
  status; `history:true` includes older candidates. “Imported” means files exist,
  not that they are referenced or visible in gameplay.
- `assets.options`: discovery of compatible add/update choices for a candidate.
- Existing create/edit operations: friendly asset names and optional `output`.
- Existing import operations: `name` accepts a friendly label; `strategy:"copy"`
  selects unused filenames, `strategy:"update"` requires `target` and reviewed
  `plan_hash` for apply. Default low-level `strategy:"new"` retains collision refusal.

Discovery reads metadata only after permission, then requests exact candidate/
managed-file read grants. UI/native updates additionally assert `daydream.asset.update`
for the selected target/plan and need edit grants for every replacement, backup and
index path. Existing permission rules still apply; no automatic allow rule is added.
UI and CLI/native adapters share the same Python rules.
Catalog status is a discovery hint; selecting a revision revalidates its artifacts.
Scanning is bounded to 2,000 directories/500 bundles; use an explicit path for
candidates outside the configured source root or beyond that limit.

Tests cover all three asset kinds, friendly labels, hidden revisions/history,
automatic collision-free copies, native grants, stable updates, preserved sidecars,
manual edits, stale plans, interruption backups and terrain identity. Actual isolated
TUI checks exercise guided add/rename/update with synthetic data; see
[validation](../validation/2026-11-07-guided-assets.md). No Potion Shop asset was moved,
updated, deleted or approved as part of this implementation.
