#!/usr/bin/env python3
"""Run a bounded Godot 4 import and optional main-scene smoke check (not a sandbox)."""

import argparse
from pathlib import Path
import re
import shlex
import subprocess
import sys


ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ERROR = re.compile(r"^\s*(?:SCRIPT ERROR|USER ERROR|ERROR|Parse Error):", re.MULTILINE)


def run(command, timeout, cwd):
    print(f"$ {shlex.join(command)}", flush=True)
    result = subprocess.run(
        command, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, errors="replace", timeout=timeout, check=False,
    )
    print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
    if result.returncode:
        raise ValueError(f"Command exited with status {result.returncode}")
    return ANSI.sub("", result.stdout)


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project", type=Path, help="trusted directory containing project.godot")
    parser.add_argument("--godot", default="godot", help="Godot 4 editor executable (not shell arguments)")
    parser.add_argument("--timeout", type=positive_int, default=120, help="seconds per process (default: 120)")
    parser.add_argument("--smoke-frames", type=positive_int, help="also run the main scene for this many iterations")
    args = parser.parse_args(argv)
    project = args.project.expanduser().resolve()
    # Resolve explicit executable paths before changing subprocess working directory.
    binary = str(Path(args.godot).expanduser().resolve()) if "/" in args.godot else args.godot

    try:
        if not (project / "project.godot").is_file():
            raise ValueError(f"No project.godot found in {project}")
        version = run([binary, "--version"], args.timeout, project)
        if not re.search(r"^4\.\d+(?:\.|$)", version, re.MULTILINE):
            raise ValueError("Expected a Godot 4 editor; select the project's pinned version")
        help_text = run([binary, "--help"], args.timeout, project)
        required = ["--headless", "--path", "--import"]
        if args.smoke_frames:
            required.append("--quit-after")
        missing = [flag for flag in required if not re.search(re.escape(flag) + r"(?=\s|$)", help_text)]
        if missing:
            raise ValueError(f"Binary does not advertise required editor flags: {', '.join(missing)}")
        print("Importing trusted project; this may run project code and write generated data.")
        commands = [[binary, "--headless", "--path", str(project), "--import"]]
        if args.smoke_frames:
            commands.append([binary, "--headless", "--path", str(project), "--quit-after", str(args.smoke_frames)])
        for command in commands:
            if ERROR.search(run(command, args.timeout, project)):
                raise ValueError("Godot reported an error even though its exit status was zero")
        print("PASS: requested processes finished with no recognized Godot error lines.")
        print("This is not full script/scene coverage, graphical validation, or a play-feel review.")
        return 0
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or b""
        print(output.decode(errors="replace") if isinstance(output, bytes) else output, end="")
        print(f"FAIL: command timed out after {args.timeout}s", file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
