import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from operations import execute, protocol
from operation_registry import find, validate
try:
    import PIL
except ImportError:
    PIL = None

SOURCE = {"schema_version": 1, "name": "dot", "width": 2, "height": 2, "palette": {"a": "#ffffff"}, "pixels": ["a.", ".a"]}


class CatalogTests(unittest.TestCase):
    def test_catalog_and_search(self):
        catalog = protocol({"action": "catalog"}, ROOT)["result"]["operations"]
        self.assertEqual(len({op["name"] for op in catalog}), len(catalog))
        self.assertEqual(protocol({"action": "search", "query": "animation.assemble"}, ROOT)["result"]["operations"][0]["name"], "animation.assemble")
        self.assertFalse(find("sprite.approve").native)

    def test_schema_rejects_unknown_fields_and_bool_dimensions(self):
        for source in ({**SOURCE, "width": True}, {**SOURCE, "surprise": "x"}):
            with self.assertRaises(ValueError): validate(find("sprite.create").schema, {"source": source, "output": "out"})

    def test_scope_and_native_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            for bundle in ("../outside", "/etc/passwd", ".env", ".git/objects"):
                result = execute("sprite.inspect", {"bundle": bundle}, directory)
                self.assertEqual(result["error"]["code"], "outside_project")
            Path(directory, "link").symlink_to(ROOT, target_is_directory=True)
            self.assertEqual(execute("sprite.inspect", {"bundle": "link"}, directory)["error"]["code"], "outside_project")
            self.assertEqual(execute("sprite.approve", {}, directory, surface="native")["error"]["code"], "unsupported")

    @unittest.skipUnless(shutil.which("node"), "Node required for native adapter tests")
    def test_native_adapter(self):
        result = subprocess.run(["node", "--test", str(ROOT / "tests" / "tools.test.mjs")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


@unittest.skipUnless(PIL, "optional Pillow required")
class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "project.godot").write_text('config_version=5\n[application]\nconfig/name="fixture"\n')

    def call(self, name, data):
        result = execute(name, data, self.root)
        self.assertTrue(result["ok"], result)
        return result

    def test_preview_create_edit_inspect_collision(self):
        data = {"source": SOURCE, "output": "art/dot-v1"}
        preview = self.call("sprite.create", data)
        self.assertEqual(preview["status"], "preview")
        self.assertFalse((self.root / "art").exists())
        self.call("sprite.create", {**data, "apply": True})
        inspected = self.call("sprite.inspect", {"bundle": "art/dot-v1"})
        self.assertEqual(preview["result"]["revision_hash"], inspected["result"]["revision_hash"])
        self.assertEqual(execute("sprite.create", data, self.root)["error"]["code"], "conflict")
        self.call("sprite.edit", {"bundle": "art/dot-v1", "patch": {"schema_version": 1, "operations": [{"op": "mirror", "axis": "horizontal"}]}, "output": "art/dot-v2", "apply": True})

    def test_native_grants_enforced_before_writes(self):
        data = {"source": SOURCE, "output": "art/dot", "apply": True}
        denied = execute("sprite.create", data, self.root, surface="native")
        self.assertEqual(denied["error"]["code"], "forbidden")
        self.assertFalse((self.root / "art").exists())
        preview = self.call("sprite.create", {**data, "apply": False})
        created = execute("sprite.create", data, self.root, surface="native", authorized=preview["access"])
        self.assertTrue(created["ok"], created)
        denied = execute("sprite.inspect", {"bundle": "art/dot"}, self.root, surface="native")
        self.assertEqual(denied["error"]["code"], "forbidden")

    def test_assemble_approve_import_and_reload(self):
        self.call("project.init", {"apply": True})
        self.call("sprite.create", {"source": SOURCE, "output": "art/a", "apply": True})
        self.call("sprite.create", {"source": {**SOURCE, "pixels": [".a", "a."]}, "output": "art/b", "apply": True})
        data = {"name": "walk", "pivot": [1, 2], "frames": [{"id": "a", "bundle": "art/a"}, {"id": "b", "bundle": "art/b"}],
                "animations": [{"name": "walk", "fps": 6, "loop": True, "frames": [{"frame": "a", "duration": 1}, {"frame": "b", "duration": 1}]}], "default_animation": "walk", "output": "art/walk", "apply": True}
        created = self.call("animation.assemble", data)
        inspected = self.call("animation.inspect", {"bundle": "art/walk"})
        self.assertEqual(inspected["result"]["frames"], ["a", "b"])
        blocked = execute("animation.import", {"bundle": "art/walk"}, self.root)
        self.assertEqual(blocked["status"], "needs_approval")
        self.call("animation.approve", {"bundle": "art/walk", "revision_hash": created["result"]["revision_hash"], "reviewer": "synthetic test", "apply": True})
        self.call("animation.import", {"bundle": "art/walk", "apply": True})

    def test_changed_import_destination_cannot_expand_native_write_grants(self):
        self.call("project.init", {"apply": True})
        created = self.call("sprite.create", {"source": SOURCE, "output": "art/dot", "apply": True})
        self.call("sprite.approve", {"bundle": "art/dot", "revision_hash": created["result"]["revision_hash"], "reviewer": "synthetic test", "apply": True})
        data = {"bundle": "art/dot"}
        preview = self.call("sprite.import", data)
        changed = execute("sprite.import", {**data, "destination": "assets/other", "apply": True}, self.root,
                          surface="native", authorized=preview["access"])
        self.assertEqual(changed["error"]["code"], "forbidden")
        self.assertFalse((self.root / "assets/other").exists())

    def test_cli_requires_apply_flag(self):
        result = subprocess.run([sys.executable, str(ROOT / "bin/daydream"), "ops", "--project", str(self.root), "call", "sprite.create", "--input", json.dumps({"source": SOURCE, "output": "art/dot", "apply": True})], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("explicit --apply", result.stdout)
        self.assertFalse((self.root / "art").exists())
