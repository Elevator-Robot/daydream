#!/usr/bin/env python3
"""Preview or install the Daydream OpenCode agent; never overwrite a destination."""

import argparse
import os
from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[1] / "agents" / "daydream.md"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir", type=Path, default=Path.home() / ".config" / "opencode",
        help="OpenCode config directory (default: ~/.config/opencode)",
    )
    parser.add_argument("--apply", action="store_true", help="create the symlink")
    args = parser.parse_args(argv)
    destination = args.config_dir.expanduser().absolute() / "agents" / "daydream.md"

    try:
        if not SOURCE.is_file():
            raise ValueError(f"Agent source is missing: {SOURCE}")
        if destination.is_symlink() and destination.resolve() == SOURCE:
            print(f"Already installed: {destination} -> {SOURCE}")
            return 0
        if os.path.lexists(destination):
            raise ValueError(f"Refusing to replace existing path: {destination}")
        print(f"{'Install' if args.apply else 'Would install'}: {destination} -> {SOURCE}")
        if not args.apply:
            print("Preview only. Run with --apply to create this symlink.")
            return 0
        destination.parent.mkdir(parents=True, exist_ok=True)
        # symlink_to is exclusive: a destination created since the check is not replaced.
        destination.symlink_to(SOURCE)
        print("Installed. Restart OpenCode to discover the daydream agent.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
