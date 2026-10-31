import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "install.py"
SOURCE = ROOT / "agents" / "daydream.md"


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)
        self.config = self.home / "config with spaces"
        self.destination = self.config / "agents" / "daydream.md"

    def install(self, *args, default=False):
        command = [sys.executable, str(SCRIPT)]
        if not default:
            command += ["--config-dir", str(self.config)]
        return subprocess.run(command + list(args), env={**os.environ, "HOME": str(self.home)}, capture_output=True, text=True)

    def test_preview_creates_nothing(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preview only", result.stdout)
        self.assertFalse(self.config.exists())

    def test_default_is_documented_global_directory(self):
        result = self.install(default=True)
        self.assertIn(str(self.home / ".config" / "opencode" / "agents" / "daydream.md"), result.stdout)
        self.assertFalse((self.home / ".config").exists())

    def test_apply_and_repeat_are_safe(self):
        self.config.mkdir()
        config_file = self.config / "opencode.json"
        config_file.write_text('{"permission":"deny"}\n')
        first = self.install("--apply")
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertTrue(self.destination.is_symlink())
        self.assertEqual(self.destination.resolve(), SOURCE)
        second = self.install("--apply")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertIn("Already installed", second.stdout)
        self.assertEqual(config_file.read_text(), '{"permission":"deny"}\n')

    def test_existing_file_is_not_overwritten(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text("user's agent\n")
        result = self.install("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.destination.read_text(), "user's agent\n")

    def test_conflicting_symlink_is_not_replaced(self):
        self.destination.parent.mkdir(parents=True)
        other = self.home / "other.md"
        other.write_text("user content")
        self.destination.symlink_to(other)
        self.assertEqual(self.install("--apply").returncode, 1)
        self.assertEqual(self.destination.resolve(), other)

    def test_dangling_symlink_is_not_replaced(self):
        self.destination.parent.mkdir(parents=True)
        other = self.home / "missing.md"
        self.destination.symlink_to(other)
        self.assertEqual(self.install("--apply").returncode, 1)
        self.assertEqual(os.readlink(self.destination), str(other))

    def test_existing_directory_is_not_replaced(self):
        self.destination.mkdir(parents=True)
        self.assertEqual(self.install("--apply").returncode, 1)
        self.assertTrue(self.destination.is_dir())

    def test_parent_file_fails_cleanly(self):
        self.config.write_text("not a directory")
        result = self.install("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.config.read_text(), "not a directory")


if __name__ == "__main__":
    unittest.main()
