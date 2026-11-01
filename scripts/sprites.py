#!/usr/bin/env python3
"""Create, preview, revise, approve, and import bounded static pixel-art sprites."""

import argparse
import json
from pathlib import Path
import sys

from sprite_core import digest, encoded, edit_source, load_revision, make_revision, read_json, source_from_png, validate_source
from sprite_store import approve_revision, import_revision, save_revision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create", help="render an editable JSON pixel specification")
    create.add_argument("spec", type=Path)
    ingest = commands.add_parser("from-png", help="convert an existing palette-limited PNG into an editable revision")
    ingest.add_argument("image", type=Path)
    ingest.add_argument("--name", required=True)
    edit = commands.add_parser("edit", help="create a new revision without modifying the original")
    edit.add_argument("bundle", type=Path)
    edit.add_argument("--patch", type=Path, required=True)
    for command in (create, ingest, edit):
        command.add_argument("--output", type=Path, required=True)
        command.add_argument("--apply", action="store_true")
    inspect = commands.add_parser("inspect", help="validate a revision and show its exact hash and preview path")
    inspect.add_argument("bundle", type=Path)
    approve = commands.add_parser("approve", help="record explicit review of an exact revision, not automated art approval")
    approve.add_argument("bundle", type=Path)
    approve.add_argument("--revision-hash", required=True)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--apply", action="store_true")
    importing = commands.add_parser("import", help="preview/apply a non-overwriting approved Godot asset import")
    importing.add_argument("bundle", type=Path)
    importing.add_argument("project", type=Path)
    importing.add_argument("--name")
    importing.add_argument("--destination", help="project-relative runtime asset directory; defaults to configured assets/sprites")
    importing.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "create":
            source = validate_source(read_json(args.spec))
            files = make_revision(source, {"method": "pixel-spec", "input_sha256": digest(encoded(source)), "license": None})
            result = save_revision(args.output, files, args.apply)
        elif args.command == "from-png":
            source, provenance = source_from_png(args.image, args.name)
            result = save_revision(args.output, make_revision(source, provenance), args.apply)
        elif args.command == "edit":
            parent = load_revision(args.bundle)
            patch = read_json(args.patch)
            source = edit_source(parent["source"], patch)
            provenance = {"method": "edit", "parent_revision_hash": parent["revision_hash"], "patch_sha256": digest(encoded(patch)),
                          "license": parent["manifest"].get("provenance", {}).get("license")}
            result = save_revision(args.output, make_revision(source, provenance), args.apply)
        elif args.command == "inspect":
            revision = load_revision(args.bundle)
            result = {"name": revision["source"]["name"], "revision_hash": revision["revision_hash"],
                      "width": revision["source"]["width"], "height": revision["source"]["height"],
                      "palette": revision["source"]["palette"], "preview": str(revision["path"] / "preview.png")}
        elif args.command == "approve":
            result = approve_revision(args.bundle, args.revision_hash, args.reviewer, args.apply)
        else:
            result = import_revision(args.bundle, args.project, args.name, args.destination, args.apply)
        print(json.dumps(result, indent=2))
        if args.command != "inspect" and not args.apply:
            print("Preview only. Add --apply to make these changes.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Sprite operation failed: {exc}. Existing assets were not replaced; inspect any partial new output before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
