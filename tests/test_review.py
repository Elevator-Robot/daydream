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
from sprite_core import encoded
from review_core import note_filename


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
                self.call("review.feedback", {**feedback, "feedback": "Also soften the outline.", "apply": True})
                inspected = self.inspect(kind)
                self.assertEqual(inspected["state"], "changes_requested")
                self.assertEqual(inspected["feedback"]["feedback"], feedback["feedback"])
                self.assertEqual([note['feedback'] for note in inspected['feedback']['notes']], [feedback['feedback'], 'Also soften the outline.'])
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
        followup = self.call("review.feedback", {**data, "feedback": "Also make the eyes bigger"})
        self.assertEqual(followup['result']['note_count'], 2)
        self.assertEqual(self.call("review.feedback", {**data, "feedback": "Also make the eyes bigger"})['result']['action'], 'keep_feedback')
        self.assertFalse(execute("review.feedback", {**data, "revision_hash": "0" * 64}, self.root)["ok"])
        self.call("sprite.edit", {"bundle": "art/dot", "patch": {"schema_version": 1, "operations": [{"op": "recolor", "symbol": "a", "color": "#112233"}]}, "output": "art/dot-v2", "apply": True})
        self.assertEqual(self.inspect("sprite", "art/dot-v2")["state"], "unreviewed")
        self.assertEqual((self.root / "art/dot/changes-requested.json").read_bytes(), before)

    def test_followup_preview_is_read_only_and_ui_requires_the_exact_new_write_grant(self):
        data = {'bundle': 'art/dot', 'kind': 'sprite', 'revision_hash': self.inspect('sprite')['revision_hash'],
                'reviewer': 'test', 'feedback': 'Darker please'}
        self.call('review.feedback', {**data, 'apply': True})
        original = (self.root/'art/dot/changes-requested.json').read_bytes()
        data['feedback'] = 'Also round the corners'
        preview = self.call('review.feedback', data)
        filename = preview['result']['file']
        self.assertFalse((self.root/'art/dot'/filename).exists())
        denied = execute('review.feedback', {**data, 'apply': True}, self.root, surface='review_ui', authorized={'reads': preview['access']['reads'], 'writes': [str(self.root/'art/dot/changes-requested.json')]})
        self.assertEqual(denied['error']['code'], 'forbidden')
        self.call('review.feedback', {**data, 'apply': True}, surface='review_ui', authorized=preview['access'])
        self.assertEqual((self.root/'art/dot/changes-requested.json').read_bytes(), original)
        self.assertTrue((self.root/'art/dot'/filename).exists())
        self.assertEqual(len(self.inspect('sprite')['feedback']['notes']), 2)

    def test_new_notes_require_read_permission_and_orphan_notes_still_block_import(self):
        data = {'bundle': 'art/dot', 'kind': 'sprite', 'revision_hash': self.inspect('sprite')['revision_hash'],
                'reviewer': 'test', 'feedback': 'Darker please', 'apply': True}
        self.call('review.feedback', data)
        prepared = execute('review.inspect', {'bundle': 'art/dot', 'kind': 'sprite'}, self.root, surface='native', prepare_only=True)
        self.call('review.feedback', {**data, 'feedback': 'Another note'})
        denied = execute('review.inspect', {'bundle': 'art/dot', 'kind': 'sprite'}, self.root, surface='native', authorized=prepared['access'])
        self.assertEqual(denied['error']['code'], 'forbidden')
        (self.root/'art/dot/changes-requested.json').unlink()
        self.assertEqual(self.inspect('sprite')['state'], 'changes_requested')
        self.assertFalse(execute('sprite.approve', {key: value for key, value in data.items() if key not in {'kind', 'feedback'}}, self.root)['ok'])
        listed = self.call('assets.list', {})['result']['assets']
        self.assertEqual(next(item for item in listed if item['bundle'] == 'art/dot')['state'], 'changes_requested')

    def test_followup_symlinks_wrong_hashes_and_oversized_history_fail_closed(self):
        data = {'bundle': 'art/dot', 'kind': 'sprite', 'revision_hash': self.inspect('sprite')['revision_hash'],
                'reviewer': 'test', 'feedback': 'Initial note', 'apply': True}
        self.call('review.feedback', data)
        saved = self.call('review.feedback', {**data, 'feedback': 'Follow-up'})['result']
        path = self.root/'art/dot'/saved['file']
        original = path.read_bytes()
        path.unlink(); path.symlink_to(self.root/'.daydream/assets.json')
        self.assertEqual(execute('review.inspect', {'bundle': 'art/dot', 'kind': 'sprite'}, self.root)['error']['code'], 'outside_project')
        path.unlink(); path.write_bytes(original)
        corrupted = json.loads(original); corrupted['revision_hash'] = '0' * 64
        path.write_bytes(encoded(corrupted))
        self.assertFalse(execute('review.inspect', {'bundle': 'art/dot', 'kind': 'sprite'}, self.root)['ok'])
        path.write_bytes(original)
        # Reach the note-count bound with valid individually identified records.
        revision = {'manifest': {'kind': 'sprite'}, 'revision_hash': data['revision_hash']}
        for i in range(30):
            record = {**json.loads(original), 'feedback': f'Note {i}'}
            (self.root/'art/dot'/note_filename(revision, 'test', record['feedback'])).write_bytes(encoded(record))
        self.assertEqual(len(self.inspect('sprite')['feedback']['notes']), 32)
        limited = execute('review.feedback', {**data, 'feedback': 'One too many'}, self.root)
        self.assertFalse(limited['ok'])
        self.assertIn('long feedback history', limited['error']['message'])
        self.assertEqual(self.call('review.feedback', data)['result']['action'], 'keep_feedback')

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
        # Includes real-backend history inspection for all kinds and optional
        # Godot serialization, not just mocked dialogs.
        result = subprocess.run(["node", "--test", str(ROOT / "tests/review.test.mjs")], capture_output=True, text=True,
                                env={**os.environ, "DAYDREAM_TEST_PYTHON": sys.executable}, timeout=120)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
