#!/usr/bin/env python3
"""Preview or initialize project-local Daydream configuration without overwrites."""

import argparse
import json
import os
from pathlib import Path
import stat
import sys
import asset_access


SCHEMA_VERSION = 1
IGNORE = "# Local artifacts; config and asset metadata remain trackable.\n/cache/\n/previews/\n/state/\n"


def validate_path(project, value):
    """Accept only project-contained, relative asset locations."""
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError("Asset paths must be nonempty relative POSIX paths")
    path = Path(value)
    if path.is_absolute() or any(part in {".", "..", ""} for part in value.split("/")):
        raise ValueError(f"Unsafe asset path: {value!r}")
    if any(part.startswith(".") for part in path.parts):
        raise ValueError(f"Asset paths cannot use hidden directories: {value!r}")
    try:
        target = (project / path).resolve()
        target.relative_to(project)
    except (ValueError, RuntimeError) as exc:
        raise ValueError(f"Asset path escapes the project: {value!r}") from exc
    if target.exists() and not target.is_dir():
        raise ValueError(f"Asset location is not a directory: {value!r}")


def validate_document(project, name, text):
    if name not in {"config.json", "assets.json"}:
        return
    data = json.loads(text)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int:
        raise ValueError(f"{name}: expected an object with an integer schema_version")
    if data["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"{name}: unsupported schema_version {data['schema_version']!r}")
    if name == "config.json":
        paths = data.get("paths")
        if not isinstance(paths, dict) or not {"assets", "sources"}.issubset(paths):
            raise ValueError("config.json: paths must contain assets and sources")
        for key in ("assets", "sources"):
            validate_path(project, paths[key])
    elif not isinstance(data.get("assets"), list) or not all(
        isinstance(asset, dict) for asset in data["assets"]
    ):
        raise ValueError("assets.json: assets must be a list of objects")


def read_existing(directory_fd, name, base=None):
    asset_access.anchored(name, base)
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    except FileNotFoundError:
        return None
    with os.fdopen(fd, "r", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError(f"Refusing non-regular file: .daydream/{name}")
        return stream.read()


def init_project(project, apply=False, assets_dir="assets", sources_dir="art"):
    """Return a file plan; apply creates missing files only in a Godot project.

    Existing files are validated and preserved byte-for-byte. No engine runs,
    asset directories, downloads, or global configuration changes are performed.
    """
    project = Path(project).expanduser().resolve(strict=True)
    if not (project / "project.godot").is_file():
        raise ValueError(f"Not a Godot project root (missing project.godot): {project}")
    defaults = {
        "config.json": json.dumps({
            "schema_version": SCHEMA_VERSION,
            "paths": {"assets": assets_dir, "sources": sources_dir},
        }, indent=2) + "\n",
        "assets.json": json.dumps({"schema_version": SCHEMA_VERSION, "assets": []}, indent=2) + "\n",
        ".gitignore": IGNORE,
        ".gdignore": "",
    }
    # Directory-relative opens prevent following a substituted metadata symlink.
    root_fd = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    directory_fd = None
    try:
        try:
            directory_fd = os.open(
                ".daydream", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd,
            )
        except FileNotFoundError:
            pass
        plan = []
        for name, default in defaults.items():
            existing = read_existing(directory_fd, name, project / ".daydream") if directory_fd is not None else None
            text = default if existing is None else existing
            validate_document(project, name, text)
            plan.append({"path": f".daydream/{name}", "action": "create" if existing is None else "keep", "content": text})
        if apply:
            for entry in plan:
                if entry["action"] == "create": asset_access.write(project / entry["path"])
            if directory_fd is None:
                os.mkdir(".daydream", dir_fd=root_fd)
                directory_fd = os.open(
                    ".daydream", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd,
                )
            for entry in plan:
                if entry["action"] == "create":
                    fd = os.open(
                        Path(entry["path"]).name,
                        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                        0o644, dir_fd=directory_fd,
                    )
                    with os.fdopen(fd, "w", encoding="utf-8") as stream:
                        stream.write(entry["content"])
        return plan
    finally:
        if directory_fd is not None:
            os.close(directory_fd)
        os.close(root_fd)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="Godot project root containing project.godot")
    parser.add_argument("--apply", action="store_true", help="create missing files after validation")
    parser.add_argument("--assets-dir", default="assets", help="default project-relative runtime asset location")
    parser.add_argument("--sources-dir", default="art", help="default project-relative editable source location")
    args = parser.parse_args(argv)
    try:
        plan = init_project(args.project, args.apply, args.assets_dir, args.sources_dir)
        for entry in plan:
            action = "Created" if args.apply else "Would create"
            print(f"{'Keep' if entry['action'] == 'keep' else action}: {entry['path']}")
            if entry["action"] == "create" and not args.apply:
                print(entry["content"], end="")
        print("Ready. Existing files preserved." if args.apply else "Preview only. Use --apply to create missing files.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Initialization failed: {exc}. No existing files were replaced; inspect any partial output before retrying.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
