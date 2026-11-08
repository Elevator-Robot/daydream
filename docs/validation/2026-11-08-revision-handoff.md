# Revision from saved feedback — 2026-11-08

## User-reported gap

After saving feedback, users had to leave review, remember an asset name, and
compose a separate chat request before Daydream made another candidate. The user
requested that continuing be part of the selected asset's flow.

## Implemented flow

`/assets` now offers **Make revised version** whenever saved feedback exists and
highlights it as the next action. Clicking it prepares a read-only, ticket-bound
request with the selected project, bundle, kind, name, revision hash and all current
notes, then submits it with the documented OpenCode V2 `session.prompt` API. The
review closes and the user follows the normal agent's progress in chat. No asset
name or path must be entered, and no extra slash command was added.

The request instructs the agent to recheck the source, preserve previous versions,
create a fresh candidate through shared edit tools, and show its preview for a
new review. Existing tool permissions and separate approval/import decisions
continue to apply. Saving a note alone or finishing review submits nothing.

## Automated checks

```sh
DAYDREAM_TEST_PYTHON=/tmp/opencode/daydream-sprites-test-venv/bin/python \
  node --test tests/review.test.mjs
python3 -m unittest discover -s tests -v
TTFX_BIN=/usr/bin/ttfx GODOT_BIN=/usr/bin/godot \
  /tmp/opencode/daydream-sprites-test-venv/bin/python -m unittest discover -s tests -v
git diff --check
```

The full optional environment passed **169 Python-discovered tests**, including
the Node suites and isolated real-Godot fixture checks. The dependency-free run
passed with **70 optional tests skipped**. The review Node suite now has **25
tests**; the targeted run passed 24 with its Godot-only case skipped, and the
full optional run includes that case.

New checks cover:

- Exact selection, latest follow-up notes and read-only preparation for sprites,
  animations and tilesets using the real shared backend.
- Expired, cross-session and changed-revision tickets; read denial and cancellation.
- Saving feedback then sending one request without an asset-name prompt.
- Finishing review without a request; active-session changes during preparation.
- Failed submission without false success/retry; repeated dispatch while sending.

## Actual OpenCode TUI check

A standalone OpenCode TUI used an isolated install/config/data/cache and synthetic
project under `/tmp/opencode/daydream-revise-ui-*`. The fixture dispatched the
registered `daydream.assets` command; candidate selection, preview confirmation
and **Make revised version** were keyboard-driven through actual dialogs.

The real `session.prompt` call admitted a message containing the exact selected
bundle/hash and both notes (“Make the outline darker” and “Keep the eyes bright
though”). The success toast appeared, review closed, and the message was visible
in chat and retrieved through the session data API. All source bundle hashes
remained unchanged, and no approval was created.

Provider execution was disabled in the fixture; OpenCode reported no available
model after admitting the request. This proves the UI/RPC/session handoff, not a
live model's creation or artistic quality of a revised candidate. No paid service,
actual user configuration or game project was used. The temporary transcript and
session dump are machine-local rather than durable acceptance evidence.

## API sources

- [V2 TUI commands/dialogs/client](https://opencode.ai/v2/docs/build/plugins/cli)
- [V2 JavaScript client](https://opencode.ai/v2/docs/build/client)
- [V2 RPC](https://opencode.ai/v2/docs/build/plugins/rpc)
- [V2 OpenAPI contract](https://opencode.ai/v2/openapi.json): `session.prompt`
  durably admits input and schedules execution unless `resume` is false.
