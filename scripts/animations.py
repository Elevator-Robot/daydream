#!/usr/bin/env python3
"""Create/revise motion previews and safely import approved Godot sprite animations."""

import argparse
import json
from pathlib import Path
import sys

import animation_core as animation
from animation_godot import outputs
from sprite_core import digest, encoded, load_revision as load_sprite, read_json
from sprite_store import approve_revision, import_revision, save_revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="build a recipe with --base, or recreate a canonical animation source")
    create.add_argument("recipe", type=Path)
    create.add_argument("--base", type=Path, help="static revision used by a recipe; omit for canonical animation source JSON")
    edit = commands.add_parser("edit", help="revise frames/timing/pivot in a fresh bundle")
    edit.add_argument("bundle", type=Path)
    edit.add_argument("--patch", type=Path, required=True)
    for command in (create, edit):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--apply", action="store_true")
    inspect = commands.add_parser("inspect", help="validate all frames, motion previews, and hashes")
    inspect.add_argument("bundle", type=Path)
    approve = commands.add_parser("approve", help="record explicit review of the entire exact animation")
    approve.add_argument("bundle", type=Path)
    approve.add_argument("--revision-hash", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--apply", action="store_true")
    importing = commands.add_parser("import", help="preview/apply approved SpriteFrames and AnimatedSprite2D resources")
    importing.add_argument("bundle", type=Path)
    importing.add_argument("project", type=Path)
    importing.add_argument("--name")
    importing.add_argument("--destination")
    importing.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            recipe = json.loads(animation.read_regular(args.recipe, animation.MAX_SOURCE_BYTES))
            if args.base is not None:
                base = load_sprite(args.base)
                source = animation.source_from_recipe(base["source"], recipe)
                provenance = {"method": "animation-recipe", "base_revision_hash": base["revision_hash"],
                              "recipe_sha256": digest(encoded(recipe)), "license": base["manifest"]["provenance"].get("license")}
            else:
                if not isinstance(recipe, dict) or "width" not in recipe or "height" not in recipe:
                    raise ValueError("Recipes need --base STATIC_REVISION; omit --base only for canonical animation source.json")
                source = animation.validate_source(recipe)
                provenance = {"method": "animation-source", "input_sha256": digest(encoded(source)), "license": None}
            result = save_revision(args.output, animation.make_revision(source, provenance), args.apply, kind=animation.KIND)
        elif args.command == "edit":
            parent = animation.load_revision(args.bundle)
            patch = read_json(args.patch)
            source = animation.edit_animation(parent["source"], patch)
            provenance = {"method": "animation-edit", "parent_revision_hash": parent["revision_hash"],
                          "patch_sha256": digest(encoded(patch)), "license": parent["manifest"]["provenance"].get("license")}
            result = save_revision(args.output, animation.make_revision(source, provenance), args.apply, kind=animation.KIND)
        elif args.command == "inspect":
            revision = animation.load_revision(args.bundle)
            result = {"name": revision["source"]["name"], "revision_hash": revision["revision_hash"],
                      "width": revision["source"]["width"], "height": revision["source"]["height"],
                      "frames": [frame["id"] for frame in revision["source"]["frames"]],
                      "pivot": revision["source"]["pivot"], "animations": revision["source"]["animations"],
                      "spritesheet": str(revision["path"] / "spritesheet.png"),
                      "preview": str(revision["path"] / "preview.html"),
                      "previews": [{"animation": clip["name"], "visual_frames": len(animation.motion_frames(revision["source"], clip)[0]),
                                    "motion": str(revision["path"] / (clip["name"] + ".motion.png")),
                                    "contact_sheet": str(revision["path"] / (clip["name"] + ".contact.png"))}
                                   for clip in revision["source"]["animations"]]}
        elif args.command == "approve":
            result = approve_revision(args.bundle, args.revision_hash, args.reviewer, args.apply, loader=animation.load_revision)
        else:
            result = import_revision(args.bundle, args.project, args.name, args.destination, args.apply,
                                     loader=animation.load_revision, output_builder=outputs)
        print(json.dumps(result, indent=2))
        if args.command != "inspect" and not args.apply:
            print("Preview only. Add --apply to make these changes.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Animation operation failed: {exc}. Existing assets were not replaced; inspect any partial new output before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
