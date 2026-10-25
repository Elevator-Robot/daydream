# Game-specific instructions — example to adapt

Do not install this template globally or replace an existing `AGENTS.md` blindly.
Fill in the facts for this game; remove sections that do not apply.

## Project contract

- Engine version and binary: `<exact version; executable/path; editor build>`
- Language and build toolchain: `<GDScript / C# / native; required versions>`
- Renderer and supported platforms: `<project's actual settings>`
- Project root and main scene: `<paths>`
- Entry points/autoloads/addons: `<important paths and purpose>`
- Design intent: `<what must feel right; what must not change>`

## Working conventions

- Follow `<existing style, scene/resource organization, typing conventions>`.
- Preserve `<stable node paths, save format, networking or other contracts>`.
- Do not modify `<generated files, vendored assets, protected areas>`.
- External services / unsafe startup behavior: `<what runs and required approval>`.

## Validation

- Read-only inspection: `<commands>`
- Build/import: `<exact pinned-binary command and any generated-file effects>`
- Unit/integration tests: `<existing commands>`
- Graphical run: `<command or editor steps, scene, expected renderer>`
- Reproduce relevant behavior: `<controls and repeatable steps>`
- Capture: `<available tool or explicit manual screenshot step>`
- Known baseline failures: `<evidence, or none observed>`
- Human play-feel review: `<specific acceptance checks>`

Record commands that actually work; do not claim nonexistent tests or tools.
