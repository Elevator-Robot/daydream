# Project-local Daydream configuration

Contributor/integration reference. For the guided setup offered during asset use,
see [Your assets](REVIEW.md).

Daydream's initialization helper creates a small `.daydream/` directory inside
an existing Godot project. It uses Python's standard library, runs no Godot code,
and requires no plugin, daemon, provider, or network access.

## Initialize or preview

Run the helper from your permanent Daydream checkout, targeting the game's root:

```sh
# Preview contents and paths; no writes.
python3 /absolute/daydream/scripts/init_project.py /absolute/game

# Create missing files only.
python3 /absolute/daydream/scripts/init_project.py /absolute/game --apply

# Match a game's established asset layout (only affects new config).
python3 /absolute/daydream/scripts/init_project.py /absolute/game \
  --assets-dir resources/art --sources-dir source-art --apply
```

The target must contain `project.godot`. Daydream does not initialize its own
tool repository as a game, discover another repository, or create a game for you.
The Python entry point is `init_project(project, apply=False, assets_dir="assets",
sources_dir="art")` in `scripts/init_project.py`; it returns a file plan and
raises on invalid inputs. The CLI exits zero on success and one on failure.

## Generated files

```text
.daydream/
  config.json   # Versioned project-relative asset location hints
  assets.json   # Empty, versioned asset metadata container
  .gitignore    # Ignores /cache/, /previews/, and /state/
  .gdignore     # Keeps tool metadata and future previews out of Godot imports
```

New `config.json`:

```json
{
  "schema_version": 1,
  "paths": {
    "assets": "assets",
    "sources": "art"
  }
}
```

Paths are relative to the Godot project root. Defaults are hints, not a migration
or a requirement to reorganize the game. These asset directories are **not**
created. Use the game's existing layout when known. Paths must be nonempty,
project-contained, non-hidden directory paths without traversal; symlinks that
resolve outside the project are rejected. No absolute paths or backslashes.

New `assets.json`:

```json
{
  "schema_version": 1,
  "assets": []
}
```

This reserves a place for provenance and approval records without inventing any.
The initializer validates only the version and list-of-objects container. The
[sprite workflow](SPRITES.md) and [animation extension](ANIMATIONS.md) write their
own versioned provenance and hash-bound approval records after validating a
revision. Other asset types still
have no record-level validator. An arbitrary entry in this file is not permission
to run a tool or proof of human review.

Both JSON files require integer `schema_version: 1`. Unknown fields are allowed
and preserved; unsupported versions and malformed required fields fail rather
than being reset or silently migrated. The config's `paths.assets` and
`paths.sources` are required. There are no provider, executable-command, model,
engine-pin, or permission fields interpreted by this helper.

## Agent behavior and consent

- Before its first authorized write task, the agent previews initialization and
  creates missing files. It uses the helper from the checkout distributing its
  instructions, not an assumed script in the game.
- No extra confirmation is needed when local initialization is within the user's
  already-authorized write task and project rules allow it.
- Read-only requests never trigger initialization. Ambiguous project selection,
  missing write authorization, or project-specific approval rules require asking
  first. OpenCode permission prompts still apply.
- The helper never prompts interactively: preview is the default and `--apply`
  is explicit. The agent handles any necessary conversation with the user.
- This behavior is defined in the agent instructions, not a runtime hook or
  guaranteed automatic callback. Actual OpenCode discovery/execution still needs
  verification on the intended machine.

## Preservation, recovery, and version control

Existing valid files are left byte-for-byte unchanged. Missing companion files
are added on rerun; existing ignore files are preserved even if they differ from
the defaults. Review custom ignore rules yourself. Other files are untouched.

The helper refuses symlinked metadata directories/files and non-regular files.
It preflights all managed files before writes and uses exclusive creation to
avoid overwrites. A failure or concurrent writer can leave a partial new setup:
inspect it, resolve the reported issue, and rerun. Initialization is not a
multi-file transaction or a sandbox against a hostile concurrent process.

Commit the config, metadata, and ignore files when appropriate for the game.
Keep secrets, chat histories, engine pins, and duplicated `AGENTS.md` instructions
out of them. Keep editable art in the game's source directories, not in metadata.
No root `.gitignore`, global OpenCode config, asset, or existing scene is modified.

To undo initialization, inspect and remove only the generated files you no longer
need. Do not delete later user metadata or original artwork. The helper performs
no deletion or automatic migration.
