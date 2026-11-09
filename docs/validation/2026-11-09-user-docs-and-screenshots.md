# End-user documentation refresh — 2026-11-09

## Request and audit

The user requested a clear, end-user-friendly GitHub README with screenshots.
The audit found ambiguity between dashboard and standalone revision-preview
controls, plus obsolete canvas descriptions still mixed into the current dashboard
reference. Historical validation records were retained, not rewritten as if the
old UI had never existed.

## Changes

- Reworked the root README around a visual collection overview, short capability
  list, ordered setup, one first-asset walkthrough and task-focused links.
- Added two actual dashboard screenshots to the README: collection and animation
  gallery. The dashboard guide includes those plus a tileset explorer screenshot.
- Kept project-specific storage schemas, architecture and validation outside the
  end-user README. Update/agent-only variants use collapsible details.
- Clarified dashboard gallery versus standalone review-viewer controls in the
  review, preview and sprite guides; cleaned obsolete current reference wording.
- Identified the still-unmerged dashboard preview and selected that branch in setup
  rather than promising these screenshots match a fresh main-branch installation.

## Screenshot evidence and source boundaries

A disposable Moonlight Workshop project used the repository's slime, floor, wall
and idle-animation examples through shared operations. Palette variants, a blink,
a shifted-row bounce and a terrain-transition set provide representative artwork.
Synthetic approval/import states demonstrate statuses, not real artwork acceptance.

The current built dashboard and real bridge/backend were rendered in isolated
Chromium. Captures waited for thumbnails, all clip images and the tile atlas to
load. The collection and tile views are full captures; the gallery is a crop of
the actual gallery element. Each image was opened and inspected. No user-game
artwork, actual configuration or project files were used or modified. Provenance
is retained in `docs/images/README.md`.

## Validation

```sh
python3 -m unittest discover -s tests -v
GODOT_BIN=/usr/bin/godot python3 -m unittest discover -s tests -p test_check_project.py -v
git diff --check
```

The dependency-free suite passed with 80 optional skips out of 182 discovered tests.
All 12 project-helper checks passed with Godot enabled, including real isolated
import/startup and broken-script fixtures. Local documentation/image links and
heading fragments resolved; screenshot dimensions/file sizes were checked.
The screenshot browser fixture reported no JavaScript exceptions.

The docs/images are local changes. No commit, push, merge or GitHub publication was
performed for this request.
