import contextlib
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("check_project", ROOT / "scripts" / "check_project.py")
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
HELP = "--headless\n--path <directory>\n--import\n--quit-after <int>\n"


class CheckTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream test ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / "project.godot").write_text("config_version=5\n")
        self.output = io.StringIO()

    def check(self, *args):
        with contextlib.redirect_stdout(self.output), contextlib.redirect_stderr(self.output):
            return CHECK.main([str(self.project), *args])

    def mock_run(self, outputs):
        return patch.object(CHECK.subprocess, "run", side_effect=[
            subprocess.CompletedProcess([], code, output) for code, output in outputs
        ])

    def test_import_uses_argument_list_and_explicit_project(self):
        with self.mock_run([(0, "4.4.stable\n"), (0, HELP), (0, "Import complete\n")]) as run:
            self.assertEqual(self.check(), 0)
        self.assertEqual(run.call_args.args[0], ["godot", "--headless", "--path", str(self.project), "--import"])
        self.assertEqual(run.call_args.kwargs["cwd"], self.project)
        self.assertEqual(run.call_args.kwargs["timeout"], 120)
        self.assertNotIn("shell", run.call_args.kwargs)

    def test_optional_smoke_runs_after_import(self):
        with self.mock_run([(0, "4.4.stable\n"), (0, HELP), (0, ""), (0, "")]) as run:
            self.assertEqual(self.check("--smoke-frames", "10", "--timeout", "5"), 0)
        self.assertEqual(run.call_count, 4)
        self.assertEqual(run.call_args.args[0][-2:], ["--quit-after", "10"])
        self.assertEqual(run.call_args.kwargs["timeout"], 5)

    def test_exit_zero_error_lines_fail(self):
        for output in ("SCRIPT ERROR: Parse Error: bad script\n", "ERROR: unavailable resource\n", "\x1b[31mERROR:\x1b[0m failure\n"):
            with self.subTest(output=output), self.mock_run([(0, "4.4.stable\n"), (0, HELP), (0, output)]) as run:
                self.assertEqual(self.check("--smoke-frames", "10"), 1)
                self.assertEqual(run.call_count, 3)

    def test_nonzero_exit_fails(self):
        with self.mock_run([(0, "4.4.stable\n"), (0, HELP), (3, "failed\n")]):
            self.assertEqual(self.check(), 1)
        self.assertIn("status 3", self.output.getvalue())

    def test_missing_project_does_not_run_binary(self):
        (self.project / "project.godot").unlink()
        with patch.object(CHECK.subprocess, "run") as run:
            self.assertEqual(self.check(), 1)
            run.assert_not_called()

    def test_unsupported_version_fails_before_import(self):
        with self.mock_run([(0, "3.6.stable\n")]) as run:
            self.assertEqual(self.check(), 1)
        self.assertEqual(run.call_count, 1)

    def test_missing_flag_fails_before_import(self):
        with self.mock_run([(0, "4.4.stable\n"), (0, "--headless\n--path <directory>\n")]) as run:
            self.assertEqual(self.check(), 1)
        self.assertEqual(run.call_count, 2)

    def test_missing_executable_is_clear(self):
        with patch.object(CHECK.subprocess, "run", side_effect=FileNotFoundError("missing Godot")):
            self.assertEqual(self.check(), 1)
        self.assertIn("missing Godot", self.output.getvalue())

    def test_timeout_reports_partial_output(self):
        with patch.object(CHECK.subprocess, "run", side_effect=subprocess.TimeoutExpired(["godot"], 120, output=b"partial output\n")):
            self.assertEqual(self.check(), 1)
        self.assertIn("partial output", self.output.getvalue())
        self.assertIn("timed out", self.output.getvalue())

    def test_invalid_limits_fail_before_running(self):
        for args in (("--timeout", "0"), ("--smoke-frames", "0"), ("--smoke-frames", "-1")):
            with self.subTest(args=args), patch.object(CHECK.subprocess, "run") as run:
                with self.assertRaises(SystemExit) as exc:
                    self.check(*args)
                self.assertEqual(exc.exception.code, 2)
                run.assert_not_called()


@unittest.skipUnless(os.environ.get("GODOT_BIN"), "set GODOT_BIN to opt into real-engine tests")
class RealGodotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream integration ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        shutil.copytree(ROOT / "tests" / "fixtures" / "smoke", self.project)
        # Keep engine settings, save data, and caches away from the user's home.
        self.env = dict(os.environ)
        for variable, folder in (("HOME", "home"), ("XDG_CONFIG_HOME", "config"),
                                 ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache")):
            path = Path(self.temp.name) / folder
            path.mkdir()
            self.env[variable] = str(path)

    def run_check(self):
        return subprocess.run([
            sys.executable, str(ROOT / "scripts" / "check_project.py"), str(self.project),
            "--godot", os.environ["GODOT_BIN"], "--smoke-frames", "10", "--timeout", "60",
        ], env=self.env, capture_output=True, text=True, timeout=300)

    def test_real_import_and_main_scene(self):
        result = self.run_check()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("smoke fixture reached _ready", result.stdout)

    def test_real_broken_script_fails(self):
        (self.project / "main.gd").write_text("extends Node\nfunc _ready( -> void:\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("FAIL:", result.stderr)
        self.assertIn("SCRIPT ERROR:", result.stdout)


if __name__ == "__main__":
    unittest.main()
