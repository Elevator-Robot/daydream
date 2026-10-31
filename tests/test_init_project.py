import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "init_project.py"
SPEC = importlib.util.spec_from_file_location("init_project", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InitProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream init ")
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "game with spaces"
        self.project.mkdir()
        (self.project / "project.godot").write_text("config_version=5\n")
        self.metadata = self.project / ".daydream"

    def run_init(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(self.project), *args],
            capture_output=True, text=True,
        )

    def test_preview_is_read_only_and_shows_defaults(self):
        result = self.run_init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"schema_version": 1', result.stdout)
        self.assertIn("Would create: .daydream/config.json", result.stdout)
        self.assertFalse(self.metadata.exists())

    def test_apply_creates_only_metadata_and_is_idempotent(self):
        plan = MODULE.init_project(self.project, apply=True)
        self.assertEqual(len(plan), 4)
        before = {p.name: p.read_bytes() for p in self.metadata.iterdir()}
        self.assertEqual(set(before), {"config.json", "assets.json", ".gitignore", ".gdignore"})
        self.assertEqual(json.loads(before["assets.json"])["assets"], [])
        self.assertEqual(set(p.name for p in self.project.iterdir()), {"project.godot", ".daydream"})
        self.assertTrue(all(entry["action"] == "keep" for entry in MODULE.init_project(self.project, apply=True)))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.metadata.iterdir()})

    def test_custom_paths_and_user_metadata_are_preserved(self):
        result = self.run_init("--apply", "--assets-dir", "game assets", "--sources-dir", "sources/art")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.metadata / "config.json"
        data = json.loads(path.read_text())
        self.assertEqual(data["paths"]["assets"], "game assets")
        data["custom"] = {"note": "preserve me"}
        path.write_text(json.dumps(data))
        before = path.read_bytes()
        result = self.run_init("--apply")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(path.read_bytes(), before)

    def test_partial_initialization_fills_missing_files(self):
        self.metadata.mkdir()
        (self.metadata / ".gitignore").write_text("# user rules\n")
        self.assertEqual(self.run_init("--apply").returncode, 0)
        self.assertEqual((self.metadata / ".gitignore").read_text(), "# user rules\n")
        self.assertTrue((self.metadata / "config.json").is_file())

    def test_existing_metadata_and_extra_files_are_not_rewritten(self):
        MODULE.init_project(self.project, apply=True)
        manifest = self.metadata / "assets.json"
        manifest.write_text('{"schema_version":1,"assets":[{"note":"user metadata"}]}')
        extra = self.metadata / "notes.txt"
        extra.write_text("leave this alone\n")
        before = {p.name: p.read_bytes() for p in self.metadata.iterdir()}
        self.assertEqual(self.run_init("--apply").returncode, 0)
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.metadata.iterdir()})

    def test_concurrently_created_file_is_not_overwritten(self):
        real_open = os.open

        def competing_open(path, flags, *args, **kwargs):
            if path == "config.json" and flags & os.O_EXCL:
                (self.metadata / "config.json").write_text("another writer's data")
            return real_open(path, flags, *args, **kwargs)

        with mock.patch.object(MODULE.os, "open", side_effect=competing_open):
            with self.assertRaises(FileExistsError):
                MODULE.init_project(self.project, apply=True)
        self.assertEqual((self.metadata / "config.json").read_text(), "another writer's data")
        self.assertFalse((self.metadata / "assets.json").exists())

    def test_invalid_existing_documents_fail_before_any_file_creation(self):
        self.metadata.mkdir()
        for text in ("broken", "[]", '{"schema_version": 2}', '{"schema_version": true}', '{"schema_version": 1, "paths": {}}'):
            with self.subTest(text=text):
                path = self.metadata / "config.json"
                path.write_text(text)
                result = self.run_init("--apply")
                self.assertEqual(result.returncode, 1)
                self.assertEqual(path.read_text(), text)
                self.assertEqual(list(self.metadata.iterdir()), [path])

    def test_invalid_manifest_blocks_writes(self):
        self.metadata.mkdir()
        path = self.metadata / "assets.json"
        path.write_text('{"schema_version": 1, "assets": ["invalid"]}')
        self.assertEqual(self.run_init("--apply").returncode, 1)
        self.assertFalse((self.metadata / "config.json").exists())

    def test_unsafe_paths_fail_without_creating_metadata(self):
        for value in ("/tmp/assets", "../outside", ".", ".git/assets", ".daydream/cache", "a/../b", "a\\b", "", "a//b"):
            with self.subTest(value=value):
                result = self.run_init("--apply", "--assets-dir", value)
                self.assertEqual(result.returncode, 1)
                self.assertFalse(self.metadata.exists())

    def test_asset_directory_symlink_cannot_escape_project(self):
        (self.project / "assets").symlink_to(self.project.parent, target_is_directory=True)
        self.assertEqual(self.run_init("--apply").returncode, 1)
        self.assertFalse(self.metadata.exists())

    def test_metadata_directory_symlinks_are_refused(self):
        for target in (self.project.parent, self.project.parent / "missing"):
            with self.subTest(target=target):
                self.metadata.symlink_to(target, target_is_directory=True)
                self.assertEqual(self.run_init("--apply").returncode, 1)
                self.assertTrue(self.metadata.is_symlink())
                self.metadata.unlink()

    def test_existing_file_directory_fifo_and_symlinks_are_not_replaced(self):
        self.metadata.write_text("user file")
        self.assertEqual(self.run_init("--apply").returncode, 1)
        self.assertEqual(self.metadata.read_text(), "user file")
        self.metadata.unlink()
        self.metadata.mkdir()
        path = self.metadata / "config.json"
        path.mkdir()
        self.assertEqual(self.run_init("--apply").returncode, 1)
        path.rmdir()
        os.mkfifo(path)
        self.assertEqual(self.run_init("--apply").returncode, 1)
        path.unlink()
        for target in (self.project / "project.godot", self.project / "missing.json"):
            with self.subTest(target=target):
                path.symlink_to(target)
                self.assertEqual(self.run_init("--apply").returncode, 1)
                self.assertTrue(path.is_symlink())
                path.unlink()

    def test_non_project_and_missing_project_are_rejected(self):
        (self.project / "project.godot").unlink()
        self.assertEqual(self.run_init("--apply").returncode, 1)
        self.assertFalse(self.metadata.exists())
        self.project.rmdir()
        self.assertEqual(self.run_init("--apply").returncode, 1)
        self.assertFalse(self.project.exists())


if __name__ == "__main__":
    unittest.main()
