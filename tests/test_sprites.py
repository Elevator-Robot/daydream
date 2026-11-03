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
import sprite_core as core
import sprite_store as store
from init_project import init_project

PILLOW = importlib.util.find_spec("PIL") is not None


def example():
    return json.loads((ROOT / "examples" / "slime.sprite.json").read_text())


class SpriteSchemaTests(unittest.TestCase):
    def test_example_source_is_a_bounded_editable_sprite(self):
        source = example()
        self.assertEqual(core.validate_source(source), source)
        self.assertEqual((source["width"], source["height"]), (32, 32))

    def test_invalid_versions_dimensions_palettes_and_rows_fail(self):
        cases = [
            ("schema_version", True), ("schema_version", 2), ("width", 0), ("height", 257), ("width", True),
            ("name", "../escape"), ("palette", {}), ("palette", {".": "#ffffff"}),
            ("palette", {"o": "#ffffff00"}), ("pixels", ["."]),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                source = example()
                source[field] = value
                with self.assertRaises(ValueError): core.validate_source(source)
        source = example()
        source["pixels"][0] = "!" * 32
        with self.assertRaises(ValueError): core.validate_source(source)

    def test_edits_are_explicit_bounded_and_do_not_change_the_source(self):
        source = example()
        original = copy.deepcopy(source)
        result = core.edit_source(source, {"schema_version": 1, "operations": [
            {"op": "recolor", "symbol": "o", "color": "#080f20"},
            {"op": "mirror", "axis": "horizontal"},
            {"op": "paint", "x": 0, "y": 0, "symbol": "g"},
            {"op": "rect", "box": [1, 0, 3, 0], "symbol": "w"},
        ]})
        self.assertEqual(source, original)
        self.assertEqual(result["palette"]["o"], "#080f20")
        self.assertEqual(result["pixels"][0][:4], "gwww")
        for op in ({"op": []}, {"op": "mirror", "axis": "diagonal"}, {"op": "paint", "x": -1, "y": 0, "symbol": "g"},
                   {"op": "rect", "box": [0, 0, 100, 0], "symbol": "g"}, {"op": "recolor", "symbol": "missing", "color": "#ffffff"}):
            with self.subTest(op=op), self.assertRaises(ValueError):
                core.edit_source(source, {"schema_version": 1, "operations": [op]})

    def test_missing_optional_dependency_has_a_clear_error(self):
        real_import = __import__
        def importing(name, *args, **kwargs):
            if name == "PIL": raise ImportError("isolated missing dependency")
            return real_import(name, *args, **kwargs)
        with mock.patch("builtins.__import__", side_effect=importing), self.assertRaisesRegex(ValueError, "optional Pillow"):
            core.pillow()


@unittest.skipUnless(PILLOW, "install optional requirements-sprites.txt in an isolated environment")
class SpriteWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="daydream sprites ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / "slime v1"
        self.files = core.make_revision(example(), {"method": "pixel-spec", "license": None})
        store.save_revision(self.bundle, self.files, apply=True)
        self.project = self.root / "game"
        self.project.mkdir()
        (self.project / "project.godot").write_text('config_version=5\n\n[application]\nconfig/name="Sprite fixture"\nrun/main_scene="res://assets/sprites/slime.tscn"\n\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        init_project(self.project, apply=True)

    def approve(self, bundle=None):
        bundle = bundle or self.bundle
        revision = core.load_revision(bundle)
        store.approve_revision(bundle, revision["revision_hash"], "isolated test reviewer", apply=True)
        return revision

    def snapshot(self, directory):
        return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob("*") if p.is_file()}

    def test_generated_png_palette_alpha_dimensions_and_nearest_preview(self):
        Image, _ = core.pillow()
        revision = core.load_revision(self.bundle)
        self.assertEqual(revision["revision_hash"], core.digest(self.files["manifest.json"]))
        with Image.open(self.bundle / "sprite.png") as image:
            self.assertEqual(image.size, (32, 32))
            self.assertEqual(image.getpixel((0, 0)), (0, 0, 0, 0))
            allowed = {tuple(bytes.fromhex(color[1:])) + (255,) for color in example()["palette"].values()}
            allowed.add((0, 0, 0, 0))
            self.assertTrue(all(image.getpixel((x, y)) in allowed for y in range(32) for x in range(32)))
        with Image.open(self.bundle / "preview.png") as image:
            self.assertEqual(image.size, (256, 256))
            self.assertEqual(image.getpixel((12 * 8, 4 * 8)), tuple(bytes.fromhex("19243b")) + (255,))

    def test_revision_preview_is_read_only_and_existing_paths_are_never_adopted(self):
        output = self.root / "new"
        store.save_revision(output, self.files)
        self.assertFalse(output.exists())
        before = self.snapshot(self.bundle)
        with self.assertRaises(ValueError): store.save_revision(self.bundle, self.files, apply=True)
        self.assertEqual(before, self.snapshot(self.bundle))
        link = self.root / "dangling"
        link.symlink_to(self.root / "missing")
        with self.assertRaises(ValueError): store.save_revision(link, self.files, apply=True)

    def test_edit_creates_new_hash_and_does_not_copy_approval_or_modify_parent(self):
        parent = self.approve()
        before = self.snapshot(self.bundle)
        changed = core.edit_source(parent["source"], json.loads((ROOT / "examples" / "slime-darker-outline.edit.json").read_text()))
        output = self.root / "slime v2"
        store.save_revision(output, core.make_revision(changed, {"method": "edit", "parent_revision_hash": parent["revision_hash"], "license": None}), apply=True)
        revision = core.load_revision(output)
        self.assertNotEqual(revision["revision_hash"], parent["revision_hash"])
        self.assertFalse((output / "approval.json").exists())
        self.assertEqual(before, self.snapshot(self.bundle))

    def test_png_ingest_preserves_pixels_and_rejects_excess_colors_or_partial_alpha(self):
        source, provenance = core.source_from_png(self.bundle / "sprite.png", "copy")
        self.assertEqual(core.image_from_source(source).tobytes(), core.image_from_source(example()).tobytes())
        self.assertEqual(provenance["method"], "png-import")
        Image, _ = core.pillow()
        for partial in (True, False):
            image = Image.new("RGBA", (40, 1))
            image.putdata([(index, 0, 0, 128 if partial else 255) for index in range(40)])
            path = self.root / "invalid.png"
            image.save(path)
            with self.assertRaises(ValueError): core.source_from_png(path, "copy")

    def test_png_ingest_refuses_oversize_non_png_and_corrupt_files(self):
        Image, _ = core.pillow()
        large = self.root / "large.png"
        Image.new("RGBA", (257, 1)).save(large)
        with self.assertRaises(ValueError): core.source_from_png(large, "copy")
        other = self.root / "not-a-png.png"
        Image.new("RGB", (4, 4)).save(other, format="GIF")
        with self.assertRaises(ValueError): core.source_from_png(other, "copy")
        other.write_bytes(b"not an image")
        with self.assertRaises(OSError): core.source_from_png(other, "copy")

    def test_approval_requires_exact_hash_and_preserves_existing_approval(self):
        revision = core.load_revision(self.bundle)
        with self.assertRaises(ValueError): store.approve_revision(self.bundle, "0" * 64, "human", apply=True)
        self.assertFalse((self.bundle / "approval.json").exists())
        store.approve_revision(self.bundle, revision["revision_hash"], "human")
        self.assertFalse((self.bundle / "approval.json").exists())
        self.approve()
        before = (self.bundle / "approval.json").read_bytes()
        store.approve_revision(self.bundle, revision["revision_hash"], "different label", apply=True)
        self.assertEqual((self.bundle / "approval.json").read_bytes(), before)

    def test_import_rejects_unapproved_and_tampered_revisions(self):
        before = self.snapshot(self.project)
        with self.assertRaisesRegex(ValueError, "approval"): store.import_revision(self.bundle, self.project, apply=True)
        self.approve()
        (self.bundle / "preview.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "hash mismatch"): store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(before, self.snapshot(self.project))

    def test_recomputed_manifest_cannot_reuse_an_old_approval(self):
        self.approve()
        path = self.bundle / "manifest.json"
        manifest = json.loads(path.read_text())
        manifest["provenance"]["note"] = "new revision identity"
        path.write_bytes(core.encoded(manifest))
        with self.assertRaisesRegex(ValueError, "stale"): store.import_revision(self.bundle, self.project)

    def test_rehashed_png_or_preview_must_still_match_the_editable_source(self):
        Image, _ = core.pillow()
        for filename in ("sprite.png", "preview.png"):
            with self.subTest(filename=filename):
                files = dict(self.files)
                with Image.open(self.bundle / filename) as image:
                    changed = image.convert("RGBA")
                changed.putpixel((0, 0), (255, 0, 255, 255))
                files[filename] = core.png_bytes(changed)
                manifest = json.loads(files["manifest.json"])
                manifest["files"][filename] = core.digest(files[filename])
                files["manifest.json"] = core.encoded(manifest)
                output = self.root / filename
                store.save_revision(output, files, apply=True)
                with self.assertRaisesRegex(ValueError, "pixels do not match|preview does not depict"):
                    core.load_revision(output)

    def test_preview_then_import_preserves_existing_records_and_sets_nearest_filter(self):
        self.approve()
        path = self.project / ".daydream" / "assets.json"
        path.write_text(json.dumps({"schema_version": 1, "custom": "keep", "assets": [{"kind": "other", "note": "user metadata"}]}))
        before = self.snapshot(self.project)
        plan = store.import_revision(self.bundle, self.project)
        self.assertEqual(len(plan["create"]), 3)
        self.assertEqual(before, self.snapshot(self.project))
        store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual((self.project / "assets/sprites/slime.png").read_bytes(), self.files["sprite.png"])
        self.assertEqual((self.project / "art/sprites/slime.json").read_bytes(), self.files["source.json"])
        self.assertIn("texture_filter = 1", (self.project / "assets/sprites/slime.tscn").read_text())
        index = json.loads(path.read_text())
        self.assertEqual(index["custom"], "keep")
        self.assertEqual(index["assets"][0]["note"], "user metadata")
        self.assertEqual(index["assets"][1]["revision_hash"], core.load_revision(self.bundle)["revision_hash"])
        self.assertFalse((self.project / ".daydream/.sprites.lock").exists())

    def test_collisions_and_existing_locks_do_not_replace_assets_or_metadata(self):
        self.approve()
        asset = self.project / "assets/sprites/slime.png"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"user asset")
        before = self.snapshot(self.project)
        with self.assertRaises(ValueError): store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(before, self.snapshot(self.project))
        asset.unlink()
        lock = self.project / ".daydream/.sprites.lock"
        lock.write_text("another operation")
        before = self.snapshot(self.project)
        with self.assertRaises(FileExistsError): store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(before, self.snapshot(self.project))

    def test_existing_import_sidecars_are_not_silently_reused(self):
        self.approve()
        sidecar = self.project / "assets/sprites/slime.png.import"
        sidecar.parent.mkdir(parents=True)
        sidecar.write_text("user resource metadata")
        before = self.snapshot(self.project)
        with self.assertRaisesRegex(ValueError, "existing asset"):
            store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(before, self.snapshot(self.project))

    def test_unsafe_paths_and_symlinked_destinations_or_metadata_are_refused(self):
        self.approve()
        for path in ("../escape", "/absolute", ".godot", "assets/../escape"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                store.import_revision(self.bundle, self.project, destination=path, apply=True)
        outside = self.root / "outside"
        outside.mkdir()
        (self.project / "assets").symlink_to(outside, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)): store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(list(outside.iterdir()), [])
        (self.project / "assets").unlink()
        inside = self.project / "elsewhere"
        inside.mkdir()
        (self.project / "assets").symlink_to(inside, target_is_directory=True)
        with self.assertRaises(OSError): store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(list(inside.iterdir()), [])
        (self.project / "assets").unlink()
        config = self.project / ".daydream/config.json"
        config.unlink()
        config.symlink_to(self.bundle / "source.json")
        with self.assertRaises(OSError): store.import_revision(self.bundle, self.project, apply=True)

    def test_symlinked_revision_files_and_directories_are_refused(self):
        alias = self.root / "alias"
        alias.symlink_to(self.bundle, target_is_directory=True)
        with self.assertRaises(OSError): core.load_revision(alias)
        path = self.bundle / "sprite.png"
        saved = self.root / "saved.png"
        path.rename(saved)
        path.symlink_to(saved)
        with self.assertRaises(OSError): core.load_revision(self.bundle)

    def test_detected_concurrent_manifest_edit_is_not_overwritten(self):
        self.approve()
        index_path = self.project / ".daydream/assets.json"
        real_write = store.write_new
        changed = b'{"schema_version": 1, "assets": [], "user_edit": true}\n'
        def writing(directory, name, data, **kwargs):
            real_write(directory, name, data, **kwargs)
            if name.startswith(".sprites-"): index_path.write_bytes(changed)
        with mock.patch.object(store, "write_new", side_effect=writing), self.assertRaisesRegex(ValueError, "concurrently"):
            store.import_revision(self.bundle, self.project, apply=True)
        self.assertEqual(index_path.read_bytes(), changed)
        self.assertFalse((self.project / ".daydream/.sprites.lock").exists())
        self.assertTrue((self.project / "assets/sprites/slime.png").exists())  # Partial outputs are not destructively rolled back.

    def test_cli_previews_without_writes_and_does_not_invent_approval(self):
        output = self.root / "cli output"
        result = subprocess.run([sys.executable, str(ROOT / "scripts/sprites.py"), "create", str(ROOT / "examples/slime.sprite.json"), "--output", str(output)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Preview only", result.stdout)
        self.assertFalse(output.exists())
        result = subprocess.run([sys.executable, str(ROOT / "scripts/sprites.py"), "import", str(self.bundle), str(self.project), "--apply"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("approval", result.stderr)

    def test_cli_create_edit_inspect_approve_and_import_in_an_isolated_fixture(self):
        def run(*args):
            result = subprocess.run([sys.executable, str(ROOT / "scripts/sprites.py"), *map(str, args)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            return result.stdout
        first, second = self.root / "cli-v1", self.root / "cli-v2"
        run("create", ROOT / "examples/slime.sprite.json", "--output", first, "--apply")
        run("edit", first, "--patch", ROOT / "examples/slime-darker-outline.edit.json", "--output", second, "--apply")
        info = json.loads(run("inspect", second))
        self.assertEqual(info["palette"]["o"], "#080f20")
        run("approve", second, "--revision-hash", info["revision_hash"], "--reviewer", "isolated test reviewer", "--apply")
        run("import", second, self.project, "--apply")
        self.assertTrue((self.project / "assets/sprites/slime.tscn").is_file())

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "set GODOT_BIN for real sprite-resource integration")
    def test_real_godot_import_scene_startup_and_texture_resource(self):
        self.approve()
        store.import_revision(self.bundle, self.project, apply=True)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/check_project.py"), str(self.project), "--godot", os.environ["GODOT_BIN"], "--smoke-frames", "3"], capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        script = self.project / "verify_sprite.gd"
        script.write_text('extends SceneTree\nfunc _init():\n\tvar packed = load("res://assets/sprites/slime.tscn")\n\tvar sprite = packed.instantiate()\n\tassert(sprite is Sprite2D)\n\tassert(sprite.texture_filter == CanvasItem.TEXTURE_FILTER_NEAREST)\n\tassert(sprite.texture.get_width() == 32)\n\tassert(sprite.texture.get_height() == 32)\n\tsprite.free()\n\tprint("SPRITE_RESOURCE_OK")\n\tquit(0)\n')
        result = subprocess.run([os.environ["GODOT_BIN"], "--headless", "--path", str(self.project), "--script", str(script), "--quit-after", "60"], capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SPRITE_RESOURCE_OK", result.stdout)


if __name__ == "__main__":
    unittest.main()
