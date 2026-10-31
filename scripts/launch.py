#!/usr/bin/env python3
"""Open an empty primary Daydream session in OpenCode without sending a prompt."""

import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


SESSION_ID = re.compile(r"ses_[A-Za-z0-9_-]{1,240}\Z")
LAUNCH_MARKER = "DAYDREAM_LAUNCH_SESSION"


class LaunchError(ValueError):
    pass


def command(binary, arguments, directory):
    try:
        result = subprocess.run(
            [binary, *arguments], cwd=directory, capture_output=True, text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise LaunchError(f"OpenCode timed out during {' '.join(arguments[:2])}") from exc
    if result.returncode:
        # Avoid dumping configuration, authentication output, or agent prompts.
        raise LaunchError(f"OpenCode failed during {' '.join(arguments[:2])} (exit {result.returncode}). Check OpenCode's diagnostics.")
    return result.stdout.strip()


def read_json(text, operation):
    try:
        return json.loads(text)
    except (ValueError, TypeError) as exc:
        raise LaunchError(f"OpenCode returned invalid JSON during {operation}") from exc


def preflight(directory, intro=True):
    binary = shutil.which("opencode")
    if not binary:
        raise LaunchError("OpenCode is missing from PATH. Install OpenCode V2 first; Daydream does not download it.")
    version = command(binary, ["--version"], directory)
    if not re.fullmatch(r"(?:opencode\s+)?v?2\.\d+(?:\.\d+)?[^\s]*", version, re.IGNORECASE):
        raise LaunchError("Daydream requires OpenCode V2. Check `opencode --version`.")
    agent = None
    # OpenCode 2.0.32 can return the builtin-only registry on a cold location.
    # Retry only this read, never the subsequent session-creation mutation.
    for attempt in range(3):
        agents = read_json(command(binary, ["debug", "agents"], directory), "agent discovery")
        if not isinstance(agents, list):
            raise LaunchError("OpenCode returned an unsupported agent discovery response")
        agent = next((item for item in agents if isinstance(item, dict) and item.get("id") == "daydream"), None)
        if agent is not None or attempt == 2:
            break
        time.sleep(0.15 * (attempt + 1))
    if not agent or agent.get("hidden") or agent.get("mode") not in {"primary", "all"}:
        raise LaunchError("The primary Daydream agent is not installed/enabled here. Preview `python3 scripts/install.py` in the Daydream checkout, then opt in with --apply.")
    warning = None
    if intro:
        config = command(binary, ["debug", "paths", "config"], directory)
        plugin = Path(config) / "plugins" / "daydream-intro" / "tui.js"
        if not plugin.is_file():
            warning = "Intro plugin is not in OpenCode's discovered config directory; opening without animation. Install with --with-launcher, or use --no-intro."
        elif not shutil.which("ttfx"):
            warning = "ttfx is missing from PATH; opening without animation. No software was installed."
    return binary, intro and warning is None, warning


def create_session(binary, directory):
    payload = {
        "title": "Daydream",
        "agent": "daydream",
        "location": {"directory": str(directory)},
    }
    response = read_json(command(binary, ["api", "post", "/api/session", "--data", json.dumps(payload)], directory), "session creation")
    session = response.get("data", response) if isinstance(response, dict) else None
    if not isinstance(session, dict) or not isinstance(session.get("id"), str) or not SESSION_ID.fullmatch(session["id"]):
        raise LaunchError("OpenCode returned an invalid session ID; an empty session may have been created. No prompt was sent.")
    if session.get("agent") != "daydream":
        raise LaunchError("OpenCode did not select Daydream for the new session. Refusing to launch a fallback agent; no prompt was sent.")
    return session["id"]


def main(argv=None, *, interactive=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=Path.cwd(), help="workspace directory (default: current directory)")
    parser.add_argument("--no-intro", action="store_true", help="open without animation; ttfx and the intro plugin are not required")
    parser.add_argument("--doctor", action="store_true", help="check dependencies and agent discovery without creating a session")
    args = parser.parse_args(argv)
    try:
        directory = args.directory.expanduser().resolve(strict=True)
        if not directory.is_dir():
            raise LaunchError(f"Not a directory: {directory}")
        if not args.doctor:
            tty = sys.stdin.isatty() and sys.stdout.isatty() if interactive is None else interactive
            if not tty:
                raise LaunchError("Open Daydream in an interactive terminal. Use --doctor for a non-interactive check.")
        binary, intro, warning = preflight(directory, intro=not args.no_intro)
        if warning:
            print(f"Daydream: {warning}", file=sys.stderr)
        if args.doctor:
            print(f"Workspace: {directory}\nOpenCode V2: ready\nDaydream agent: ready\nIntro: {'ready' if intro else 'off or unavailable'}")
            print("No session created; no prompt sent or game files changed.")
            return 0
        session_id = create_session(binary, directory)
        environment = dict(os.environ)
        # A session-scoped, client-local opt-in; not a permanent startup flag.
        environment.pop(LAUNCH_MARKER, None)
        if intro:
            environment[LAUNCH_MARKER] = session_id
        print(f"Opening Daydream in {directory}", flush=True)
        try:
            os.execvpe(binary, [binary, "--session", session_id, str(directory)], environment)
        except OSError as exc:
            raise LaunchError(f"Could not open OpenCode. The empty session is {session_id}; no prompt was sent.") from exc
        return 0  # Reached only by an injected exec in tests.
    except KeyboardInterrupt:
        print("Daydream: cancelled.", file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Daydream: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
