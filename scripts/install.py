#!/usr/bin/env python3
"""Preview or install Daydream's agent and optional intro; never overwrite paths."""

import argparse
import os
from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[1] / "agents" / "daydream.md"
INTRO_SOURCE = SOURCE.parents[1] / "plugins" / "daydream-intro"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir", type=Path, default=Path.home() / ".config" / "opencode",
        help="OpenCode config directory (default: ~/.config/opencode)",
    )
    parser.add_argument("--apply", action="store_true", help="create the symlink")
    parser.add_argument("--with-intro", action="store_true", help="also link the optional OpenCode V2 TUI laser intro plugin")
    args = parser.parse_args(argv)
    config = args.config_dir.expanduser().absolute()
    links = [(SOURCE, config / "agents" / "daydream.md")]
    if args.with_intro:
        links.append((INTRO_SOURCE, config / "plugins" / "daydream-intro"))

    try:
        pending = []
        # Preflight every requested link before making any changes.
        for source, destination in links:
            if not source.exists():
                raise ValueError(f"Source is missing: {source}")
            if destination.is_symlink() and destination.resolve() == source:
                print(f"Already installed: {destination} -> {source}")
                continue
            if os.path.lexists(destination):
                raise ValueError(f"Refusing to replace existing path: {destination}")
            pending.append((source, destination))
        for source, destination in pending:
            print(f"{'Install' if args.apply else 'Would install'}: {destination} -> {source}")
        if not args.apply:
            print("Preview only. Run with --apply to create the requested symlinks.")
            return 0
        for source, destination in pending:
            destination.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive: a destination created since the check is not replaced.
            destination.symlink_to(source, target_is_directory=source.is_dir())
        print("Installed. Restart OpenCode to discover the daydream agent.")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
