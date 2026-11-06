import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from operations import execute
from review_fixture import create


@unittest.skipUnless(importlib.util.find_spec("PIL"), "optional Pillow required")
class ReviewCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundles = create(self.root)

    def call(self, op, data, **kwargs):
        result = execute(op, data, self.root, **kwargs)
        self.assertTrue(result["ok"], result)
        return result

    def inspect(self, kind, bundle=None):
        return self.call("review.inspect", {"kind": kind, "bundle": bundle or self.bundles[kind]})["result"]

    def test_all_asset_types_share_feedback_and_whole_revision_approval(self):
        for kind, bundle in self.bundles.items():
            with self.subTest(kind=kind):
                status = self.inspect(kind)
                self.assertEqual(status["state"], "unreviewed")
                data = {"bundle": bundle, "revision_hash": status["revision_hash"], "reviewer": "synthetic reviewer"}
                self.call(kind + ".approve", {**data, "apply": True})
                self.assertEqual(self.inspect(kind)["state"], "approved")
                feedback = {**data, "kind": kind, "feedback": "Revise the colors and alignment."}
                self.call("review.feedback", feedback)
                self.assertFalse((self.root / bundle / "changes-requested.json").exists())
                self.call("review.feedback", {**feedback, "apply": True})
                inspected = self.inspect(kind)
                self.assertEqual(inspected["state"], "changes_requested")
                self.assertEqual(inspected["feedback"]["feedback"], feedback["feedback"])
                self.assertTrue((self.root / bundle / "approval.json").exists())
                self.assertFalse(execute(kind + ".approve", {**data, "apply": True}, self.root)["ok"])
                self.assertFalse(execute(kind + ".import", {"bundle": bundle, "apply": True}, self.root)["ok"])
                self.assertFalse((self.root / bundle / ".review.lock").exists())
        self.assertFalse((self.root / "assets").exists())

    def test_feedback_is_immutable_hash_bound_and_new_revisions_start_unreviewed(self):
        status = self.inspect("sprite")
        data = {"bundle": "art/dot", "kind": "sprite", "revision_hash": status["revision_hash"], "reviewer": "test", "feedback": "Darker please", "apply": True}
        self.call("review.feedback", data)
        before = (self.root / "art/dot/changes-requested.json").read_bytes()
        self.assertEqual(self.call("review.feedback", data)["result"]["action"], "keep_feedback")
        self.assertEqual(execute("review.feedback", {**data, "feedback": "overwrite"}, self.root)["error"]["code"], "conflict")
        self.assertFalse(execute("review.feedback", {**data, "revision_hash": "0" * 64}, self.root)["ok"])
        self.call("sprite.edit", {"bundle": "art/dot", "patch": {"schema_version": 1, "operations": [{"op": "recolor", "symbol": "a", "color": "#112233"}]}, "output": "art/dot-v2", "apply": True})
        self.assertEqual(self.inspect("sprite", "art/dot-v2")["state"], "unreviewed")
        self.assertEqual((self.root / "art/dot/changes-requested.json").read_bytes(), before)

    def test_native_tools_cannot_decide_and_ui_surface_requires_exact_grants(self):
        status = self.inspect("sprite")
        data = {"bundle": "art/dot", "revision_hash": status["revision_hash"], "reviewer": "test", "apply": True}
        self.assertFalse(execute("sprite.approve", data, self.root, surface="native")["ok"])
        denied = execute("sprite.approve", data, self.root, surface="review_ui")
        self.assertEqual(denied["error"]["code"], "forbidden")
        self.assertFalse((self.root / "art/dot/approval.json").exists())
        preview = self.call("sprite.approve", {**data, "apply": False})
        self.call("sprite.approve", data, surface="review_ui", authorized=preview["access"])
        self.assertEqual(self.inspect("sprite")["state"], "approved")

    def test_import_plan_hash_covers_outputs_revision_and_metadata(self):
        status = self.inspect("sprite")
        self.call("sprite.approve", {"bundle": "art/dot", "revision_hash": status["revision_hash"], "reviewer": "test", "apply": True})
        data = {"bundle": "art/dot", "revision_hash": status["revision_hash"]}
        preview = self.call("sprite.import", data)["result"]
        self.assertFalse(execute("sprite.import", {**data, "revision_hash": "0" * 64, "apply": True}, self.root)["ok"])
        self.assertFalse(execute("sprite.import", {**data, "name": "other", "plan_hash": preview["plan_hash"], "apply": True}, self.root)["ok"])
        index = self.root / ".daydream/assets.json"
        contents = json.loads(index.read_text()); contents["note"] = "concurrent metadata change"
        index.write_text(json.dumps(contents))
        blocked = execute("sprite.import", {**data, "plan_hash": preview["plan_hash"], "apply": True}, self.root)
        self.assertFalse(blocked["ok"])
        self.assertIn("plan changed", blocked["error"]["message"])
        self.assertFalse((self.root / "assets").exists())
        new_plan = self.call("sprite.import", data)["result"]
        self.call("sprite.import", {**data, "plan_hash": new_plan["plan_hash"], "apply": True})

    def test_existing_review_lock_and_symlink_feedback_are_refused(self):
        status = self.inspect("sprite")
        lock = self.root / "art/dot/.review.lock"; lock.write_text("someone else's operation")
        data = {"bundle": "art/dot", "revision_hash": status["revision_hash"], "reviewer": "test", "apply": True}
        self.assertEqual(execute("sprite.approve", data, self.root)["error"]["code"], "conflict")
        self.assertEqual(lock.read_text(), "someone else's operation")
        lock.unlink()
        (self.root / "art/dot/changes-requested.json").symlink_to(self.root / ".daydream/assets.json")
        self.assertEqual(execute("sprite.approve", data, self.root)["error"]["code"], "outside_project")


class ReviewAdapterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node required")
    def test_review_ui_and_service(self):
        result = subprocess.run(["node", "--test", str(ROOT / "tests/review.test.mjs")], capture_output=True, text=True,
                                env={**os.environ, "DAYDREAM_TEST_PYTHON": sys.executable}, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
