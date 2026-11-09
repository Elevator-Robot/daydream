# Contributor and integration references

These documents describe internal formats, CLI/native adapters, persistence,
permission boundaries and verification. They are not the user onboarding path.
The task-focused [user guide](../README.md) should remain free of those details.

- [Asset lifecycle](ASSET_LIFECYCLE.md): naming, automatic revision paths, discovery,
  guarded updates, recovery snapshots and concurrency limitations.
- [Review and approval](REVIEW.md): exact-revision decisions, shared implementation,
  import-plan binding and user-interface boundaries.
- [Preview](PREVIEW.md): runtime process management, browser delivery and advanced setup.
- [Project dashboard](PROJECT_DASHBOARD.md): refreshable workspace, shared reads,
  client-owned loopback transport and the [reviewed design](PROJECT_DASHBOARD_DESIGN.md).
- [Editor-visible layouts](EDITOR_LAYOUTS.md): engine resolution, isolated serialization
  and persistent cell verification.
- [Tilesets](TILESETS.md): source contracts, terrain generation, seam evidence and imports.
- [Collisions](COLLISIONS.md): polygon validation, coordinate conventions and Godot physics.
- [Operation protocol](../OPERATIONS.md): catalog, schemas and native/CLI adapter behavior.
- [Static sprite reference](../SPRITES.md) and [animation reference](../ANIMATIONS.md).
- [Development](../DEVELOPMENT.md), [roadmap](../ROADMAP.md), and
  [validation records](../validation/).

User-facing changes must update the relevant task guide with the actual menu
labels and outcomes. Keep implementation algorithms, RPC identifiers, JSON
schemas, locks, hashes and test harness details here or in validation/research docs.
User guides may explain effects such as “this updates an asset already used by
the game” or “your manual edits are protected” without exposing their mechanism.
