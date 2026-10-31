from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AgentTests(unittest.TestCase):
    def test_agent_has_minimal_frontmatter_without_privilege_overrides(self):
        text = (ROOT / "agents" / "daydream.md").read_text()
        parts = text.split("---\n", 2)
        self.assertEqual(parts[0], "")
        metadata = dict(line.split(": ", 1) for line in parts[1].strip().splitlines())
        self.assertEqual(set(metadata), {"description", "mode"})
        self.assertEqual(metadata["mode"], "all")
        self.assertTrue(metadata["description"])
        self.assertIn("Daydream", metadata["description"])
        self.assertIn("AGENTS.md", parts[2])
        self.assertIn("play-feel", parts[2])

    def test_agent_explains_initialization_and_authorization(self):
        text = (ROOT / "agents" / "daydream.md").read_text()
        self.assertIn("scripts/init_project.py", text)
        self.assertIn("--apply", text)
        self.assertIn("Do not ask an extra confirmation", text)
        self.assertIn("do not create it for a", text.lower())
        self.assertIn("read-only", text)
        self.assertIn("not an automatically installed hook", text)


if __name__ == "__main__":
    unittest.main()
