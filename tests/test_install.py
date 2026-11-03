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
        self.assertFalse((self.home / ".local").exists())
        self.assertEqual(result.stdout.count("Would install:"), 4)

    def test_native_tools_are_default_previewable_and_repeatable(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Would install:"), 4)
        self.assertFalse(self.config.exists())
        result = self.install("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        tools = self.config / "plugins" / "daydream-tools"
        self.assertTrue(tools.is_symlink())
        self.assertTrue((tools / "index.js").exists())
        self.assertEqual(self.install("--apply").returncode, 0)

    def test_tools_collision_blocks_all_links(self):
        tools = self.config / "plugins" / "daydream-tools"
        tools.mkdir(parents=True)
        result = self.install("--apply")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.destination.exists())

    def test_standard_reinstall_adds_tools_to_existing_install(self):
        self.assertEqual(self.install("--apply").returncode, 0)
        tools = self.config / "plugins" / "daydream-tools"
        tools.unlink()  # Simulate the previous three-link installation in this fixture.
        preview = self.install()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(preview.stdout.count("Would install:"), 1)
        self.assertFalse(tools.exists())
        self.assertEqual(self.install("--apply").returncode, 0)
        self.assertEqual(tools.resolve(), ROOT / "plugins" / "daydream-tools")

    def test_redundant_with_tools_flag_is_removed(self):
        self.assertEqual(self.install("--with-tools").returncode, 2)
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
        self.assertEqual((self.config / "plugins" / "daydream-intro").resolve(), ROOT / "plugins" / "daydream-intro")
        self.assertEqual((self.home / ".local" / "bin" / "daydream").resolve(), ROOT / "bin" / "daydream")
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

    def test_intro_preview_creates_nothing(self):
        result = self.install("--with-intro")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.config / "plugins" / "daydream-intro"), result.stdout)
        self.assertFalse(self.config.exists())

    def test_intro_is_opt_in_and_repeatable(self):
        self.assertEqual(self.install("--agent-only", "--apply").returncode, 0)
        self.assertFalse((self.config / "plugins").exists())
        self.assertEqual(self.install("--with-intro", "--apply").returncode, 0)
        self.assertFalse((self.home / ".local").exists())
        plugin = self.config / "plugins" / "daydream-intro"
        self.assertTrue(plugin.is_symlink())
        self.assertEqual(plugin.resolve(), ROOT / "plugins" / "daydream-intro")
        self.assertEqual(self.install("--with-intro", "--apply").returncode, 0)

    def test_intro_collision_blocks_agent_install(self):
        plugin = self.config / "plugins" / "daydream-intro"
        plugin.parent.mkdir(parents=True)
        plugin.write_text("user plugin")
        result = self.install("--with-intro", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.destination.exists())
        self.assertEqual(plugin.read_text(), "user plugin")

    def test_launcher_preview_includes_all_four_links_without_writes(self):
        result = self.install("--with-launcher")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(str(self.home / ".local" / "bin" / "daydream"), result.stdout)
        self.assertIn(str(self.config / "plugins" / "daydream-intro"), result.stdout)
        self.assertIn(str(self.config / "plugins" / "daydream-tools"), result.stdout)
        self.assertEqual(result.stdout.count("Would install:"), 4)
        self.assertFalse(self.config.exists())
        self.assertFalse((self.home / ".local").exists())

    def test_agent_only_preview_and_apply_request_exactly_one_link(self):
        result = self.install("--agent-only")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.count("Would install:"), 1)
        self.assertFalse(self.config.exists())
        self.assertEqual(self.install("--agent-only", "--apply").returncode, 0)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse((self.config / "plugins").exists())
        self.assertFalse((self.home / ".local").exists())

    def test_agent_only_does_not_remove_a_previously_installed_full_setup(self):
        self.assertEqual(self.install("--apply").returncode, 0)
        self.assertEqual(self.install("--agent-only", "--apply").returncode, 0)
        self.assertTrue((self.config / "plugins" / "daydream-intro").is_symlink())
        self.assertTrue((self.config / "plugins" / "daydream-tools").is_symlink())
        self.assertTrue((self.home / ".local" / "bin" / "daydream").is_symlink())

    def test_conflicting_install_modes_fail_without_writes(self):
        for flags in (("--agent-only", "--with-intro"), ("--agent-only", "--with-launcher"), ("--with-intro", "--with-launcher")):
            with self.subTest(flags=flags):
                self.assertEqual(self.install(*flags, "--apply").returncode, 2)
                self.assertFalse(self.config.exists())
                self.assertFalse((self.home / ".local").exists())

    def test_launcher_apply_and_repeat_preserve_other_commands(self):
        bin_dir = self.home / "custom bin"
        bin_dir.mkdir()
        (bin_dir / "other").write_text("keep me")
        for _ in range(2):
            result = self.install("--with-launcher", "--bin-dir", str(bin_dir), "--apply")
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((bin_dir / "daydream").resolve(), ROOT / "bin" / "daydream")
        self.assertTrue(os.access(bin_dir / "daydream", os.X_OK))
        self.assertEqual((bin_dir / "other").read_text(), "keep me")
        self.assertTrue((self.config / "plugins" / "daydream-intro").is_symlink())

    def test_launcher_collision_preflights_before_agent_or_plugin_install(self):
        command = self.home / ".local" / "bin" / "daydream"
        command.parent.mkdir(parents=True)
        command.write_text("user command")
        result = self.install("--with-launcher", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(command.read_text(), "user command")
        self.assertFalse(self.config.exists())

    def test_launcher_parent_file_blocks_all_requested_writes(self):
        bin_dir = self.home / "occupied bin"
        bin_dir.write_text("keep this file")
        result = self.install("--with-launcher", "--bin-dir", str(bin_dir), "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(bin_dir.read_text(), "keep this file")
        self.assertFalse(self.config.exists())


if __name__ == "__main__":
    unittest.main()
