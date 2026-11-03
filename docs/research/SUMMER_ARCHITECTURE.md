# Summer architecture study and Daydream decisions

Reviewed 2026-11-03 from public source only. Reference revision:
[`e77453453ee0b5bc8f7fe094826fc8d3b02b0447`](https://github.com/SummerEngine/summer/tree/e77453453ee0b5bc8f7fe094826fc8d3b02b0447).
No Summer code was executed, installed, or copied into Daydream's implementation.
No hosted service, credentials, paid generation, or closed editor was accessed.

## What the source actually does

| Evidence at the pinned revision | Observed strategy | Daydream decision |
| --- | --- | --- |
| [`src/core/ops/contract.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/core/ops/contract.ts) | Stable `area.action` IDs, effect/approval/provider metadata, one structured answer/error vocabulary | Use stable operation IDs and uniform results, with honest local-only states. No fake cloud jobs or approval URLs. |
| [`src/core/ops/catalog.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/core/ops/catalog.ts) | Discoverable catalog and input schemas, compatibility mappings, local tool runners | Define each Daydream operation once with its handler, schema, path authority, and native availability. |
| [`src/core/ops/search.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/core/ops/search.ts) | Weighted plain-language discovery over IDs, titles, tags, and summaries | Provide small offline search/describe entry points. Do not copy the ranking implementation or build a registry compiler for a tiny catalog. |
| [`src/cli/commands/ops.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/cli/commands/ops.ts) | CLI operation search/describe/call, schema-directed inputs, structured errors, dry runs | Add `daydream ops search/describe/call`; preserve the terminal launcher and legacy helpers. Our previews should run actual non-writing planning, not only assert valid input. |
| [`src/core/capabilities/tool-dispatch.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/core/capabilities/tool-dispatch.ts) | Shared low-level behavior behind CLI and MCP, plus a hand-maintained dispatch registration mirror | Keep existing Python asset behavior; derive native registration from the same canonical catalog rather than adding a second operation map. |
| [`src/mcp/tool-results.ts`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/src/mcp/tool-results.ts) | Compact results, controlled truncation, useful recovery hints | Return bounded JSON and explicit artifact paths. Do not dump source pixels or pretend a path means an image was viewed. |
| [`docs/design/CONTRACT.md`](https://github.com/SummerEngine/summer/blob/e77453453ee0b5bc8f7fe094826fc8d3b02b0447/docs/design/CONTRACT.md) | Descriptors, parity checks, shared behavior, versioned identity, evidence, and a roadmap of intended consolidation | Test CLI/native schema and behavior parity. Distinguish this design document's older/planned statements from current runtime code; not every aspiration is implemented. |

Summer therefore supports **both tools and CLI**, not merely helper scripts.
Its public agent layer and closed desktop editor are different components; this
review cannot establish private editor internals or complete feature parity.

## Measured Daydream gap

Read-only inspection of the user's Potion Shop candidates found staged static
revision bundles, shopkeeper walk/presentation atlases, contact sheets, and GIFs.
Game-local Python generators called Daydream's static helpers and separately
packed GIF previews. The project asset index was empty and the walk-v2 notes
explicitly said staged/not approved/not imported. No game files were changed or
run during that inspection, and contact sheets are not motion review.

The important gap is not folder flatness: an agent currently has to discover
scripts, construct commands, and compose pieces itself. A reusable **assemble
existing frame revisions** operation addresses that observed gap better than
only wrapping the existing recipe command.

## Product direction, not a clone

Daydream is a Summer Engine alternative targeting stock Godot and OpenCode.
Adopt the useful patterns: discoverable capabilities, shared execution, typed
inputs, consistent outcomes, deliberate preview/apply, and retained evidence.
Do not assume Summer's defaults, cloud, account system, telemetry, transport,
licensing, or editor requirements are suitable here.

Initial transport: documented **native OpenCode V2 tools** and a CLI over the
same local Python capability implementation. No MCP server or daemon is needed.
Common actions get direct tool names; search/describe/call cover the catalog.
No arbitrary Python module, executable, shell flag, provider, or engine command
is accepted as an operation input.

Improvements we can establish rather than claim:

- One authored operation/schema/handler definition, with schema parity tests.
- Actual backend previews validate collisions and approval state without writes.
- Native operations are scoped to the active session's project and honor read/
  edit permissions before their respective effects; no model-selected project
  switch or shell fallback around a denial.
- Whole-revision approval stays in the shared core. Initial native tools do not
  write approval records; documented CLI approval still requires explicit human
  review. There is no claim of authenticated identity or an inviolable sandbox.
- Cancellation and timeouts report possibly partial work; writes are not retried.
  Existing collision refusal is not advertised as durable idempotency.
- No auto-install of Pillow and no change to existing game candidates merely to
  migrate their layout. CLI fallback remains usable without the native plugin.

The catalog/native adapter implementation and its validation status belong in
the roadmap. This research note is not itself evidence that those tools ship.
