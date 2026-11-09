# Information beneath compared artwork — 2026-11-09

The user requested better use of the empty area beneath comparison images.
Comparison now removes the external metadata rail and places each version's
information directly below its own image. The reference shows dimensions, state,
saved time, palette and feedback. The selected candidate retains its complete
information and exact-source review command. Single-image mode retains its compact
side panel. Metadata is rendered once, not duplicated or switched to the reference.

Checks completed:

```sh
# dashboard/
npm run check
npm run build

# repository root
python3 -m unittest discover -s tests -v
GODOT_BIN=/usr/bin/godot python3 -m unittest discover -s tests -p test_check_project.py -v
git diff --check
```

The actual isolated Nyx gallery fixture verified two comparison panels, metadata
below each respective image, exactly one selected-candidate information panel and
restoration of the sidebar when comparison is disabled. All five linked animation
previews, frame inspection and the responsive gallery still passed without browser
JavaScript errors. The actual screenshot was opened and visually inspected: both
palettes, version-specific notes and the selected review action are legible below
their matching previews. No user project, approval or imported asset was changed.

Temporary capture: `/tmp/opencode/daydream-nyx-gallery-*/.comparison-info.png`.
These fixture observations are not human artwork approval or gameplay acceptance.

## Follow-up: consistent normal and comparison layout

The user requested information below the image at all times, not just while
comparing. The selected image panel now always owns its information. It occupies
the first column in both modes, with a constant preview label and reserved selector
row. The reference is added second rather than moving the candidate across columns.

The browser fixture checks identical selected-image x/y/width and information y
coordinates before and after enabling comparison, exactly one information panel,
and information beneath the preview in both modes. Type checking, production build,
the dependency-free suite and isolated real-Godot checks passed. The updated browser
gallery check passed without JavaScript exceptions.

## Final direction: adaptive desktop information placement

The user then explicitly requested information to the right while Compare is off,
moving underneath when Compare is on. CSS now changes the layout of the same
information element, with a short named View Transition where supported. Reduced
motion bypasses that animation; narrow layouts remain stacked.

The browser fixture verifies right-of-image placement in normal mode, below-image
placement during comparison, restoration after toggling off, and preservation of
the same DOM information panel. Reduced-motion emulation confirms no transition
is started. At 600 pixels the panel remains below the image with no horizontal
overflow. Actual screenshots were inspected. Type checks, production build,
dependency-free unit suite, isolated Godot checks and `git diff --check` passed.

## Fixed image panels and matching metadata

The user requested unchanged image-window dimensions while toggling comparison.
Selected/reference preview windows now share a 360 × 220 pixel desktop footprint;
comparison stacks below 820 pixels instead of squeezing them into narrow columns.
On smaller viewports the shared responsive width applies equally to both modes.
Browser assertions verify unchanged selected width/height and identical reference
dimensions at desktop and 600-pixel widths.

Both information panels now use the same `AssetFacts` renderer and compact styling
for dimensions, unit labels and palette/clip counts. Review-state badges occupy
matching heading rows while preserving each version's actual state. The actual
comparison screenshot was inspected and the browser gallery/placement checks,
TypeScript/build, dependency-free tests and isolated Godot checks passed.
