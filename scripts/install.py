#!/usr/bin/env python3
"""Preview or install Daydream's launcher, agent, and intro; never overwrite paths."""

import argparse
import os
from pathlib import Path
import sys


SOURCE = Path(__file__).resolve().parents[1] / "agents" / "daydream.md"
INTRO_SOURCE = SOURCE.parents[1] / "plugins" / "daydream-intro"
LAUNCHER_SOURCE = SOURCE.parents[1] / "bin" / "daydream"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config-dir", type=Path, default=Path.home() / ".config" / "opencode",
        help="OpenCode config directory (default: ~/.config/opencode)",
    )
    parser.add_argument("--apply", action="store_true", help="create the requested symlinks (otherwise preview only)")
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--agent-only", action="store_true", help="install only the OpenCode agent, without launcher or intro")
    selection.add_argument("--with-intro", action="store_true", help="compatibility mode: agent and intro only, without launcher")
    selection.add_argument("--with-launcher", action="store_true", help="install the full setup (the default; retained for compatibility)")
    parser.add_argument("--bin-dir", type=Path, default=Path.home() / ".local" / "bin", help="launcher directory (default: ~/.local/bin; unused in agent-only/intro-only modes)")
    args = parser.parse_args(argv)
    with_launcher = not (args.agent_only or args.with_intro)
    config = args.config_dir.expanduser().absolute()
    links = [(SOURCE, config / "agents" / "daydream.md")]
    if not args.agent_only:
        links.append((INTRO_SOURCE, config / "plugins" / "daydream-intro"))
    if with_launcher:
        links.append((LAUNCHER_SOURCE, args.bin_dir.expanduser().absolute() / "daydream"))

    try:
        pending = []
        if with_launcher and not os.access(LAUNCHER_SOURCE, os.X_OK):
            raise ValueError(f"Launcher source is not executable: {LAUNCHER_SOURCE}")
        # Preflight every requested link before making any changes.
        for source, destination in links:
            if not source.exists():
                raise ValueError(f"Source is missing: {source}")
            if destination.is_symlink() and destination.resolve() == source:
                print(f"Already installed: {destination} -> {source}")
                continue
            if os.path.lexists(destination):
                raise ValueError(f"Refusing to replace existing path: {destination}")
            for parent in destination.parents:
                if os.path.lexists(parent) and not parent.is_dir():
                    raise ValueError(f"Destination parent is not a directory: {parent}")
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
        if with_launcher:
            bin_dir = str(args.bin_dir.expanduser().absolute())
            if bin_dir not in os.environ.get("PATH", "").split(os.pathsep):
                print(f"Launcher installed, but {bin_dir} is not on PATH. Use its full path or add that directory yourself.")
            else:
                print("Start with: daydream [directory]")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Installation failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
