import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("daydream_launch", ROOT / "scripts" / "launch.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

FAKE = '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with open(os.environ["FAKE_LOG"], "a") as log:
    log.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\\n")
if args == ["--version"]:
    print(os.environ.get("FAKE_VERSION", "opencode v2.0.32"))
elif args == ["debug", "agents"]:
    calls = [json.loads(line) for line in Path(os.environ["FAKE_LOG"]).read_text().splitlines()]
    cold = os.environ.get("FAKE_COLD_AGENTS") and sum(call["args"] == args for call in calls) == 1
    print('[]' if cold else os.environ.get("FAKE_AGENTS", '[{"id":"daydream","mode":"all","hidden":false}]'))
elif args == ["debug", "paths", "config"]:
    print(os.environ["FAKE_CONFIG"])
elif args[:3] == ["api", "post", "/api/session"]:
    if os.environ.get("FAKE_API_FAIL"):
        print("private diagnostic that must not be dumped", file=sys.stderr)
        sys.exit(7)
    print(os.environ.get("FAKE_SESSION", '{"data":{"id":"ses_test123","agent":"daydream"}}'))
else:
    sys.exit(9)
'''


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream launch ")
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.directory = self.home / "game with spaces"
        self.directory.mkdir()
        self.bin = self.home / "bin"
        self.bin.mkdir()
        self.opencode = self.bin / "opencode"
        self.opencode.write_text(FAKE)
        self.opencode.chmod(0o755)
        ttfx = self.bin / "ttfx"
        ttfx.write_text("#!/bin/sh\nexit 0\n")
        ttfx.chmod(0o755)
        self.config = self.home / "config"
        plugin = self.config / "plugins" / "daydream-intro" / "tui.js"
        plugin.parent.mkdir(parents=True)
        plugin.write_text("// isolated fixture\n")
        self.log = self.home / "calls.jsonl"
        self.env = mock.patch.dict(os.environ, {
            "HOME": str(self.home), "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_CONFIG": str(self.config), "FAKE_LOG": str(self.log),
        })
        self.env.start()
        self.addCleanup(self.env.stop)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()] if self.log.exists() else []

    def run_main(self, *args, interactive=True):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), mock.patch.object(MODULE.os, "execvpe") as execute:
            code = MODULE.main([str(self.directory), *args], interactive=interactive)
        return code, stdout.getvalue(), stderr.getvalue(), execute

    def test_launch_selects_agent_without_prompt_model_or_permissions_override(self):
        code, _, error, execute = self.run_main()
        self.assertEqual(code, 0, error)
        payload = json.loads(next(call["args"][-1] for call in self.calls() if call["args"][:1] == ["api"]))
        self.assertEqual(payload, {"title": "Daydream", "agent": "daydream", "location": {"directory": str(self.directory)}})
        binary, arguments, environment = execute.call_args.args
        self.assertEqual(arguments, [binary, "--session", "ses_test123", str(self.directory)])
        self.assertEqual(environment[MODULE.LAUNCH_MARKER], "ses_test123")
        self.assertTrue(all(call["cwd"] == str(self.directory) for call in self.calls()))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_no_intro_ignores_missing_optional_dependencies_and_removes_stale_marker(self):
        (self.bin / "ttfx").unlink()
        with mock.patch.dict(os.environ, {MODULE.LAUNCH_MARKER: "ses_old"}):
            code, _, error, execute = self.run_main("--no-intro")
        self.assertEqual(code, 0, error)
        self.assertNotIn(MODULE.LAUNCH_MARKER, execute.call_args.args[2])
        self.assertFalse(any(call["args"] == ["debug", "paths", "config"] for call in self.calls()))

    def test_missing_plugin_warns_but_opens_agent_without_intro(self):
        (self.config / "plugins" / "daydream-intro" / "tui.js").unlink()
        code, _, error, execute = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("without animation", error)
        self.assertNotIn(MODULE.LAUNCH_MARKER, execute.call_args.args[2])

    def test_missing_ttfx_warns_without_installing_or_starting_it(self):
        real_which = MODULE.shutil.which
        with mock.patch.object(MODULE.shutil, "which", side_effect=lambda name: None if name == "ttfx" else real_which(name)):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 0)
        self.assertIn("ttfx is missing", error)
        self.assertNotIn(MODULE.LAUNCH_MARKER, execute.call_args.args[2])

    def test_doctor_is_noninteractive_and_creates_no_session_or_files(self):
        code, output, error, execute = self.run_main("--doctor", interactive=False)
        self.assertEqual(code, 0, error)
        self.assertIn("No session created", output)
        execute.assert_not_called()
        self.assertFalse(any(call["args"][:1] == ["api"] for call in self.calls()))
        self.assertEqual(list(self.directory.iterdir()), [])

    def test_noninteractive_launch_fails_before_any_opencode_command(self):
        code, _, error, execute = self.run_main(interactive=False)
        self.assertEqual(code, 1)
        self.assertIn("interactive terminal", error)
        self.assertEqual(self.calls(), [])
        execute.assert_not_called()

    def test_missing_opencode_and_old_version_fail_without_session(self):
        with mock.patch.object(MODULE.shutil, "which", return_value=None):
            code, _, error, _ = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("OpenCode is missing", error)
        with mock.patch.dict(os.environ, {"FAKE_VERSION": "opencode v1.2.0"}):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("requires OpenCode V2", error)
        execute.assert_not_called()

    def test_missing_hidden_or_subagent_only_agent_never_falls_back_to_build(self):
        for agent in ([], [{"id": "daydream", "mode": "subagent"}], [{"id": "daydream", "mode": "all", "hidden": True}]):
            with self.subTest(agent=agent), mock.patch.dict(os.environ, {"FAKE_AGENTS": json.dumps(agent)}):
                code, _, error, execute = self.run_main()
                self.assertEqual(code, 1)
                self.assertIn("not installed/enabled", error)
                execute.assert_not_called()
        self.assertFalse(any(call["args"][:1] == ["api"] for call in self.calls()))

    def test_cold_agent_discovery_retries_only_the_read_not_session_creation(self):
        with mock.patch.dict(os.environ, {"FAKE_COLD_AGENTS": "1"}):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 0, error)
        self.assertEqual(sum(call["args"] == ["debug", "agents"] for call in self.calls()), 2)
        self.assertEqual(sum(call["args"][:1] == ["api"] for call in self.calls()), 1)
        execute.assert_called_once()

    def test_bad_agent_json_and_bad_session_responses_fail_safely(self):
        with mock.patch.dict(os.environ, {"FAKE_AGENTS": "bad json"}):
            self.assertEqual(self.run_main()[0], 1)
        for response in ("bad json", '[]', '{"data":{"id":"--auto","agent":"daydream"}}', '{"data":{"id":"ses_valid","agent":"build"}}'):
            with self.subTest(response=response), mock.patch.dict(os.environ, {"FAKE_SESSION": response}):
                code, _, _, execute = self.run_main()
                self.assertEqual(code, 1)
                execute.assert_not_called()

    def test_api_failure_does_not_dump_private_diagnostics(self):
        with mock.patch.dict(os.environ, {"FAKE_API_FAIL": "1"}):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 1)
        self.assertNotIn("private diagnostic", error)
        execute.assert_not_called()

    def test_exec_failure_reports_session_without_deleting_it(self):
        with mock.patch.object(MODULE.os, "execvpe", side_effect=OSError("cannot exec")), contextlib.redirect_stderr(io.StringIO()) as error, contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(MODULE.main([str(self.directory)], interactive=True), 1)
        self.assertIn("ses_test123", error.getvalue())
        self.assertFalse(any("delete" in call["args"] for call in self.calls()))

    def test_invalid_directory_and_subprocess_timeout_are_clear(self):
        self.directory.rmdir()
        self.assertEqual(self.run_main()[0], 1)
        self.directory.mkdir()
        with mock.patch.object(MODULE.subprocess, "run", side_effect=subprocess.TimeoutExpired("opencode", 30)):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 1)
        self.assertIn("timed out", error)
        execute.assert_not_called()

    def test_ctrl_c_during_preflight_exits_cleanly_without_session_creation(self):
        with mock.patch.object(MODULE.subprocess, "run", side_effect=KeyboardInterrupt):
            code, _, error, execute = self.run_main()
        self.assertEqual(code, 130)
        self.assertIn("cancelled", error)
        self.assertNotIn("Traceback", error)
        execute.assert_not_called()

    def test_launcher_help_works_through_a_symlink_outside_checkout(self):
        link = self.bin / "daydream"
        link.symlink_to(ROOT / "bin" / "daydream")
        result = subprocess.run([str(link), "--help"], cwd=self.directory, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("--no-intro", result.stdout)
        self.assertIn("--doctor", result.stdout)
        self.assertEqual(self.calls(), [])


if __name__ == "__main__":
    unittest.main()
