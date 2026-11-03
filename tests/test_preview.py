import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class PreviewTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required for preview integration tests")
    def test_preview_service_and_slash_command(self):
        result = subprocess.run(["node", "--test", str(ROOT / "tests/preview.test.mjs")],
                                env={**os.environ, "DAYDREAM_TEST_PYTHON": sys.executable},
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(shutil.which("node"), "Node required for syntax checks")
    def test_entrypoints_parse(self):
        for name in ("tui.js", "rpc.js", "index.js"):
            with self.subTest(name=name):
                result = subprocess.run(["node", "--check", str(ROOT / "plugins/daydream-tools" / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
