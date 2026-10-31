from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("node"), "Node.js is optional; needed only for intro plugin tests")
class IntroTests(unittest.TestCase):
    def test_animation_and_lifecycle(self):
        result = subprocess.run(
            [shutil.which("node"), "--test", str(ROOT / "tests" / "intro.test.mjs"),
             str(ROOT / "tests" / "open-daydream.test.mjs")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_plugin_entrypoint_syntax(self):
        result = subprocess.run(
            [shutil.which("node"), "--check", str(ROOT / "plugins" / "daydream-intro" / "tui.js")],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
