import copy
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
sys.path.insert(0, str(ROOT / "scripts"))
import animation_core as core
from animation_godot import outputs
import sprite_core as sprites
import sprite_store as store
from operations import execute
from operation_registry import find
from init_project import init_project

PILLOW = importlib.util.find_spec("PIL") is not None


def base():
    return json.loads((ROOT / "examples/slime.sprite.json").read_text())


def recipe():
    return json.loads((ROOT / "examples/slime-idle.animation.json").read_text())


def source():
    return core.source_from_recipe(base(), recipe())


def large_source(count=76, steps=129):
    sprite = {'schema_version': 1, 'name': 'large', 'width': 4, 'height': 4,
              'palette': {'a': '#556677', 'b': '#aabbcc'}, 'pixels': ['aaaa'] * 4}
    frames = []
    for index in range(count):
        pixels = ''.join('b' if index & (1 << bit) else 'a' for bit in range(16))
        frames.append({'id': f'f{index}', 'source': {**copy.deepcopy(sprite), 'pixels': [pixels[start:start + 4] for start in range(0, 16, 4)]}})
    return {'schema_version': 1, 'name': 'large', 'width': 4, 'height': 4, 'pivot': [2, 4],
            'frames': frames, 'animations': [{'name': 'all_frames', 'fps': 30, 'loop': True,
                'frames': [{'frame': f'f{index % count}', 'duration': 1} for index in range(steps)]}],
            'default_animation': 'all_frames'}


class AnimationSchemaTests(unittest.TestCase):
    def test_frame_and_timeline_counts_have_no_arbitrary_schema_ceiling(self):
        value = large_source(193, 257)
        self.assertIs(core.validate_source(value), value)
        for name in ('animation.create', 'animation.assemble'):
            schema = find(name).schema
            frame_schema = schema['properties']['frames'] if name.endswith('assemble') else schema['properties']['recipe']['properties']['frames']
            self.assertNotIn('maxItems', frame_schema)
            clips = schema['properties']['animations'] if name.endswith('assemble') else schema['properties']['recipe']['properties']['animations']
            self.assertNotIn('maxItems', clips['items']['properties']['frames'])
        recipe_value = {key: copy.deepcopy(value[key]) for key in ('schema_version', 'name', 'pivot', 'animations', 'default_animation')}
        recipe_value['frames'] = [{'id': frame['id'], 'pixels': frame['source']['pixels']} for frame in value['frames']]
        rebuilt = core.source_from_recipe(value['frames'][0]['source'], recipe_value)
        self.assertEqual(len(rebuilt['frames']), 193)
        self.assertEqual(len(rebuilt['animations'][0]['frames']), 257)

    def test_resource_budgets_replace_frame_count_limits_and_contact_scale_stays_positive(self):
        value = large_source()
        with mock.patch.object(core, 'MAX_ATLAS_PIXELS', 10):
            with self.assertRaisesRegex(ValueError, 'atlas.*budget'): core.validate_source(value)
        with mock.patch.object(core, 'MAX_PREVIEW_RGBA_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'decoded-memory budget'): core.validate_source(value)
        with mock.patch.object(core, 'MAX_SOURCE_BYTES', 10):
            with self.assertRaisesRegex(ValueError, 'source.*budget'): core.validate_source(value)
        long_clip = large_source(2, 1200)
        scale, cell_w, cell_h, columns, rows = core.contact_geometry(long_clip, long_clip['animations'][0])
        self.assertGreaterEqual(scale, 1)
        self.assertGreater(rows * cell_h, 2048)
        with mock.patch.object(core, 'MAX_CONTACT_PIXELS', 10):
            with self.assertRaisesRegex(ValueError, 'contact sheet.*budget'): core.validate_source(value)

    def test_recipe_has_explicit_order_durations_loop_and_pivot(self):
        value = source()
        self.assertEqual(value["pivot"], [16, 30])
        self.assertEqual([frame["id"] for frame in value["frames"]], ["open", "half", "closed", "opening"])
        self.assertEqual([step["frame"] for step in value["animations"][0]["frames"]], ["open", "half", "closed", "opening"])
        self.assertEqual([round(step["duration"] / 8 * 1000) for step in value["animations"][0]["frames"]], [1500, 100, 150, 100])
        self.assertTrue(value["animations"][0]["loop"])

    def test_recipe_does_not_change_base_and_supports_explicit_pixel_frames(self):
        original = base()
        before = copy.deepcopy(original)
        value = recipe()
        value["frames"][1] = {"id": "half", "pixels": list(original["pixels"])}
        core.source_from_recipe(original, value)
        self.assertEqual(original, before)

    def test_duplicate_unknown_frame_names_and_invalid_pivots_fail(self):
        for pivot in ([-1, 0], [33, 0], [True, 0], [0], "center"):
            value = source(); value["pivot"] = pivot
            with self.subTest(pivot=pivot), self.assertRaises(ValueError): core.validate_source(value)
        for target in ("duplicate-frame", "unknown-frame", "duplicate-animation", "default", "frame-path"):
            value = source()
            if target == "duplicate-frame": value["frames"][1]["id"] = "open"
            if target == "unknown-frame": value["animations"][0]["frames"][0]["frame"] = "missing"
            if target == "duplicate-animation": value["animations"].append(copy.deepcopy(value["animations"][0]))
            if target == "default": value["default_animation"] = "missing"
            if target == "frame-path": value["frames"][0]["id"] = "../escape"
            with self.subTest(target=target), self.assertRaises(ValueError): core.validate_source(value)

    def test_dimension_palette_timing_and_resource_bounds_are_strict(self):
        for key, invalid in (("fps", 0), ("fps", True), ("fps", float("nan")), ("fps", float("inf")), ("fps", 10**500), ("loop", 1)):
            value = source(); value["animations"][0][key] = invalid
            with self.subTest(key=key, invalid=str(invalid)[:30]), self.assertRaises(ValueError): core.validate_source(value)
        for duration in (0, -1, True, float("nan"), 0.0001, 1000):
            value = source(); value["animations"][0]["frames"][0]["duration"] = duration
            with self.subTest(duration=duration), self.assertRaises(ValueError): core.validate_source(value)
        value = source(); value["frames"][1]["source"]["palette"]["o"] = "#000000"
        with self.assertRaisesRegex(ValueError, "same palette"): core.validate_source(value)
        value = source(); value["frames"][1]["source"]["height"] = 31; value["frames"][1]["source"]["pixels"].pop()
        with self.assertRaisesRegex(ValueError, "same canvas"): core.validate_source(value)
        value = source(); value["frames"] = value["frames"] * 9
        with self.assertRaises(ValueError): core.validate_source(value)

    def test_animation_edits_are_new_data_and_global_recolor_preserves_palette_consistency(self):
        original = source()
        before = copy.deepcopy(original)
        changed = core.edit_animation(original, {"schema_version": 1, "operations": [
            {"op": "recolor", "symbol": "o", "color": "#000000"},
            {"op": "frame", "id": "open", "patch": {"schema_version": 1, "operations": [{"op": "paint", "x": 0, "y": 0, "symbol": "g"}]}},
            {"op": "pivot", "value": [16, 32]},
        ]})
        self.assertEqual(original, before)
        self.assertTrue(all(frame["source"]["palette"]["o"] == "#000000" for frame in changed["frames"]))
        self.assertEqual(changed["frames"][0]["source"]["pixels"][0][0], "g")
        self.assertEqual(changed["pivot"], [16, 32])


@unittest.skipUnless(PILLOW, "install optional requirements-sprites.txt for animation rendering tests")
class AnimationWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream animations ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.base_bundle = self.root / "static"
        store.save_revision(self.base_bundle, sprites.make_revision(base(), {"method": "pixel-spec", "license": None}), apply=True)
        self.bundle = self.root / "idle v1"
        self.source = source()
        self.files = core.make_revision(self.source, {"method": "animation-recipe", "license": None})
        store.save_revision(self.bundle, self.files, apply=True, kind=core.KIND)
        self.project = self.root / "game"
        self.project.mkdir()
        (self.project / "project.godot").write_text('config_version=5\n\n[application]\nconfig/name="Animation fixture"\nrun/main_scene="res://assets/sprites/slime_idle.tscn"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        init_project(self.project, apply=True)

    def approve(self):
        revision = core.load_revision(self.bundle)
        store.approve_revision(self.bundle, revision["revision_hash"], "isolated animation test reviewer", apply=True, loader=core.load_revision)
        return revision

    def snapshot(self, path):
        return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob("*") if file.is_file()}

    def test_large_animation_renders_inspects_edits_and_imports_without_losing_frames(self):
        value = large_source()
        files = core.make_revision(value, {'method': 'animation-source', 'license': None})
        bundle = self.root / 'large'
        store.save_revision(bundle, files, apply=True, kind=core.KIND)
        loaded = core.load_revision(bundle)
        self.assertEqual(len(loaded['source']['frames']), 76)
        self.assertEqual(len(loaded['source']['animations'][0]['frames']), 129)
        with sprites.open_image(files['all_frames.motion.png']) as image:
            self.assertEqual(image.n_frames, 129)
        with sprites.open_image(files['spritesheet.png']) as image:
            self.assertEqual(image.size, (32, 40))
        before = self.snapshot(bundle)
        edited = core.edit_animation(value, {'schema_version': 1, 'operations': [{'op': 'pivot', 'value': [1, 4]}]})
        self.assertEqual(len(edited['frames']), 76)
        store.approve_revision(bundle, loaded['revision_hash'], 'synthetic large animation', apply=True, loader=core.load_revision)
        imported = store.import_revision(bundle, self.project, apply=True, loader=core.load_revision, output_builder=outputs)
        resource = (self.project / 'assets/sprites/large.frames.tres').read_text()
        self.assertIn('AtlasTexture_75', resource)
        self.assertEqual(resource.count('"duration":'), 129)
        self.assertEqual({name: data for name, data in self.snapshot(bundle).items() if name != 'approval.json'}, before)
        if os.environ.get('GODOT_BIN'):
            script = self.project / 'verify_large.gd'
            script.write_text('''extends SceneTree
func _init():
    var frames = load("res://assets/sprites/large.frames.tres")
    assert(frames.get_frame_count("all_frames") == 129)
    assert(frames.get_frame_texture("all_frames", 75).region == Rect2(12, 36, 4, 4))
    print("LARGE_ANIMATION_OK")
    quit(0)
''')
            run = subprocess.run([os.environ['GODOT_BIN'], '--headless', '--editor', '--path', str(self.project), '--import'], capture_output=True, text=True, timeout=60)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            run = subprocess.run([os.environ['GODOT_BIN'], '--headless', '--path', str(self.project), '--script', str(script)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('LARGE_ANIMATION_OK', run.stdout)

    def test_shared_native_create_and_assembly_accept_more_than_32_frames(self):
        root = self.root / 'operation-project'; root.mkdir(); (root / 'project.godot').write_text('config_version=5\n')
        source_value = large_source(76, 76)
        seed = source_value['frames'][0]['source']
        created = execute('sprite.create', {'source': seed, 'apply': True}, root)
        self.assertTrue(created['ok'], created)
        base_bundle = created['result']['directory']
        data = {'name': 'large', 'pivot': [2, 4], 'frames': [{'id': f'f{index}', 'bundle': base_bundle} for index in range(76)],
                'animations': source_value['animations'], 'default_animation': 'all_frames'}
        prepared = execute('animation.assemble', data, root, surface='native', prepare_only=True)
        self.assertTrue(prepared['ok'], prepared)
        grants = {'reads': prepared['access']['reads'], 'writes': []}
        preview = execute('animation.assemble', data, root, surface='native', authorized=grants)
        self.assertTrue(preview['ok'], preview)
        applied = execute('animation.assemble', {**data, 'apply': True}, root, surface='native', authorized=preview['access'])
        self.assertTrue(applied['ok'], applied)
        self.assertEqual(len(core.load_revision(applied['result']['directory'])['source']['frames']), 76)
        recipe_value = {key: source_value[key] for key in ('schema_version', 'name', 'pivot', 'animations', 'default_animation')}
        recipe_value['frames'] = [{'id': frame['id'], 'pixels': frame['source']['pixels']} for frame in source_value['frames']]
        created = execute('animation.create', {'base': base_bundle, 'recipe': recipe_value, 'apply': True}, root)
        self.assertTrue(created['ok'], created)
        self.assertEqual(len(core.load_revision(created['result']['directory'])['source']['frames']), 76)

    def test_actual_preview_frames_timing_loop_atlas_and_contact_sheet(self):
        revision = core.load_revision(self.bundle)
        self.assertEqual(revision["revision_hash"], sprites.digest(self.files["manifest.json"]))
        with sprites.open_image(self.files["idle.motion.png"]) as image:
            self.assertEqual(image.n_frames, 4)
            self.assertEqual(image.info["loop"], 0)
            durations = []
            for index in range(image.n_frames):
                image.seek(index); durations.append(round(image.info["duration"]))
            self.assertEqual(durations, [1500, 100, 150, 100])
        with sprites.open_image(self.files["spritesheet.png"]) as image:
            self.assertEqual(image.size, (128, 32))
            self.assertEqual(image.crop((0, 0, 32, 32)).tobytes(), sprites.image_from_source(base()).tobytes())
        with sprites.open_image(self.files["idle.contact.png"]) as image:
            self.assertTrue(all(value <= 2048 for value in image.size))
        self.assertNotIn(b"http", self.files["preview.html"])
        self.assertNotIn(b"<script", self.files["preview.html"])

    def test_adjacent_identical_frames_merge_preview_holds_without_changing_timeline(self):
        value = source()
        value["animations"][0]["frames"] = [{"frame": "open", "duration": 1}, {"frame": "open", "duration": 2}]
        files = core.make_revision(value, {"method": "animation-recipe", "license": None})
        output = self.root / "held"
        store.save_revision(output, files, apply=True, kind=core.KIND)
        revision = core.load_revision(output)
        self.assertEqual(len(revision["source"]["animations"][0]["frames"]), 2)
        with sprites.open_image(files["idle.motion.png"]) as image:
            self.assertEqual(image.n_frames, 1)
            self.assertNotIn("duration", image.info)  # Static visual state; source/Godot still hold for 375 ms.

    def test_non_loop_preview_and_multiple_named_animations(self):
        value = source()
        blink = copy.deepcopy(value["animations"][0]); blink["name"] = "blink_once"; blink["loop"] = False
        value["animations"].append(blink)
        output = self.root / "clips"
        files = core.make_revision(value, {"method": "animation-recipe", "license": None})
        store.save_revision(output, files, apply=True, kind=core.KIND)
        core.load_revision(output)
        with sprites.open_image(files["blink_once.motion.png"]) as image: self.assertEqual(image.info["loop"], 1)

    def test_revisions_preserve_original_approval_and_require_new_approval_after_timing_changes(self):
        parent = self.approve()
        before = self.snapshot(self.bundle)
        changed = core.edit_animation(parent["source"], json.loads((ROOT / "examples/slime-slower.animation-edit.json").read_text()))
        output = self.root / "idle v2"
        store.save_revision(output, core.make_revision(changed, {"method": "animation-edit", "license": None}), apply=True, kind=core.KIND)
        revision = core.load_revision(output)
        self.assertNotEqual(parent["revision_hash"], revision["revision_hash"])
        self.assertFalse((output / "approval.json").exists())
        self.assertEqual(before, self.snapshot(self.bundle))
        with self.assertRaises(ValueError): store.validate_approval(revision, json.loads((self.bundle / "approval.json").read_text()))

    def test_animation_approval_binds_all_artifacts_and_static_approval_cannot_substitute(self):
        revision = self.approve()
        approval = json.loads((self.bundle / "approval.json").read_text())
        self.assertEqual(approval["schema_version"], 2)
        self.assertEqual(approval["files"], revision["manifest"]["files"])
        store.approve_revision(self.base_bundle, sprites.load_revision(self.base_bundle)["revision_hash"], "isolated static reviewer", apply=True)
        static = json.loads((self.base_bundle / "approval.json").read_text())
        with self.assertRaises(ValueError): store.validate_approval(revision, static)
        (self.bundle / "idle.motion.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"): core.load_revision(self.bundle)

    def test_rehashed_wrong_motion_pixels_timing_or_html_are_refused(self):
        for filename in ("idle.motion.png", "idle.contact.png", "preview.html"):
            with self.subTest(filename=filename):
                files = dict(self.files)
                files[filename] = files[filename] + b"invalid" if filename == "preview.html" else sprites.png_bytes(sprites.image_from_source(base()))
                manifest = json.loads(files["manifest.json"]); manifest["files"][filename] = sprites.digest(files[filename]); files["manifest.json"] = sprites.encoded(manifest)
                output = self.root / filename
                store.save_revision(output, files, apply=True, kind=core.KIND)
                with self.assertRaises(ValueError): core.load_revision(output)

    def test_rehashed_valid_apng_with_wrong_timing_or_loop_is_refused(self):
        for wrong in ("timing", "loop"):
            value = copy.deepcopy(self.source)
            if wrong == "timing": value["animations"][0]["frames"][0]["duration"] = 8
            else: value["animations"][0]["loop"] = False
            files = dict(self.files)
            files["idle.motion.png"] = core.motion_png(value, value["animations"][0])
            manifest = json.loads(files["manifest.json"])
            manifest["files"]["idle.motion.png"] = sprites.digest(files["idle.motion.png"])
            files["manifest.json"] = sprites.encoded(manifest)
            output = self.root / ("wrong-" + wrong)
            store.save_revision(output, files, apply=True, kind=core.KIND)
            with self.subTest(wrong=wrong), self.assertRaisesRegex(ValueError, "timing|loop"):
                core.load_revision(output)

    def test_import_is_preview_first_and_preserves_unrelated_records(self):
        self.approve()
        index_path = self.project / ".daydream/assets.json"
        original_record = {"kind": "other", "name": "user_asset", "note": "keep this"}
        index_path.write_text(json.dumps({"schema_version": 1, "custom": "preserve", "assets": [original_record]}))
        before = self.snapshot(self.project)
        plan = store.import_revision(self.bundle, self.project, loader=core.load_revision, output_builder=outputs)
        self.assertEqual(len(plan["create"]), 4)
        self.assertEqual(before, self.snapshot(self.project))
        store.import_revision(self.bundle, self.project, apply=True, loader=core.load_revision, output_builder=outputs)
        scene = (self.project / "assets/sprites/slime_idle.tscn").read_text()
        self.assertIn('type="AnimatedSprite2D"', scene)
        self.assertIn("offset = Vector2(-16, -30)", scene)
        self.assertIn("centered = false", scene)
        self.assertIn("texture_filter = 1", scene)
        index = json.loads(index_path.read_text())
        self.assertEqual(index["custom"], "preserve")
        self.assertEqual(index["assets"][0], original_record)
        record = index["assets"][-1]
        self.assertEqual(record["kind"], core.KIND)
        self.assertEqual(record["approval"]["schema_version"], 2)
        after = self.snapshot(self.project)
        with self.assertRaises(ValueError): store.import_revision(self.bundle, self.project, apply=True, loader=core.load_revision, output_builder=outputs)
        self.assertEqual(after, self.snapshot(self.project))

    def test_unapproved_or_symlinked_bundle_cannot_be_imported(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            store.import_revision(self.bundle, self.project, loader=core.load_revision, output_builder=outputs)
        alias = self.root / "alias"; alias.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaises(OSError): core.load_revision(alias)

    def test_cli_create_inspect_edit_approve_import(self):
        def run(*args):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/animations.py"), *map(str, args)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout
        first, second = self.root / "cli-v1", self.root / "cli-v2"
        run("create", ROOT / "examples/slime-idle.animation.json", "--base", self.base_bundle, "--output", first)
        self.assertFalse(first.exists())
        run("create", ROOT / "examples/slime-idle.animation.json", "--base", self.base_bundle, "--output", first, "--apply")
        run("edit", first, "--patch", ROOT / "examples/slime-slower.animation-edit.json", "--output", second, "--apply")
        info = json.loads(run("inspect", second))
        self.assertEqual(info["animations"][0]["fps"], 6)
        run("approve", second, "--revision-hash", info["revision_hash"], "--reviewer", "isolated animation test reviewer", "--apply")
        run("import", second, self.project, "--apply")
        self.assertTrue((self.project / "assets/sprites/slime_idle.frames.tres").is_file())

    def test_archived_canonical_source_can_rebuild_a_fresh_unapproved_bundle(self):
        output = self.root / "rebuilt"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/animations.py"), "create", str(self.bundle / "source.json"), "--output", str(output), "--apply"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(core.load_revision(output)["source"], self.source)
        self.assertFalse((output / "approval.json").exists())

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "set GODOT_BIN for actual animation resource/playback checks")
    def test_real_godot_frame_order_timing_loop_pivot_and_playback_progress(self):
        value = copy.deepcopy(self.source)
        once = copy.deepcopy(value["animations"][0])
        once["name"], once["loop"] = "blink_once", False
        once["frames"].reverse()
        value["animations"].append(once)
        self.bundle = self.root / "native clips"
        store.save_revision(self.bundle, core.make_revision(value, {"method": "animation-recipe", "license": None}), apply=True, kind=core.KIND)
        self.approve()
        store.import_revision(self.bundle, self.project, apply=True, loader=core.load_revision, output_builder=outputs)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check_project.py"), str(self.project), "--godot", os.environ["GODOT_BIN"], "--smoke-frames", "3"], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        verify = self.project / "verify_animation.gd"
        verify.write_text('''extends SceneTree
func _init():
    call_deferred("verify")
func verify():
    var sprite = load("res://assets/sprites/slime_idle.tscn").instantiate()
    root.add_child(sprite)
    assert(sprite is AnimatedSprite2D)
    assert(sprite.texture_filter == CanvasItem.TEXTURE_FILTER_NEAREST)
    assert(sprite.offset == Vector2(-16, -30))
    assert(not sprite.centered)
    var frames = sprite.sprite_frames
    assert(frames.get_frame_count("idle") == 4)
    assert(is_equal_approx(frames.get_animation_speed("idle"), 8.0))
    if frames.has_method("get_animation_loop_mode"):
        assert(frames.get_animation_loop_mode("idle") == 1)
    else:
        assert(frames.get_animation_loop("idle"))
    assert(is_equal_approx(frames.get_frame_duration("idle", 0), 12.0))
    assert(is_equal_approx(frames.get_frame_duration("idle", 1), 0.8))
    assert(frames.get_frame_count("blink_once") == 4)
    if frames.has_method("get_animation_loop_mode"):
        assert(frames.get_animation_loop_mode("blink_once") == 0)
    else:
        assert(not frames.get_animation_loop("blink_once"))
    assert(frames.get_frame_texture("blink_once", 0).region == Rect2(96, 0, 32, 32))
    for index in range(4):
        var texture = frames.get_frame_texture("idle", index)
        assert(texture is AtlasTexture)
        assert(texture.region == Rect2(index * 32, 0, 32, 32))
    assert(sprite.is_playing())
    var changed = false
    for step in range(100):
        await process_frame
        if sprite.frame != 0:
            changed = true
    assert(changed)
    sprite.play("blink_once")
    for step in range(140):
        await process_frame
    assert(not sprite.is_playing())
    assert(sprite.frame == 3)
    sprite.queue_free()
    print("ANIMATION_RESOURCE_AND_PLAYBACK_OK")
    quit(0)
''')
        result = subprocess.run([os.environ["GODOT_BIN"], "--headless", "--path", str(self.project), "--fixed-fps", "60", "--script", str(verify), "--quit-after", "400"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ANIMATION_RESOURCE_AND_PLAYBACK_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
