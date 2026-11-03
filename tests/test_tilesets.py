import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import sprite_core as sprite
import tileset_core as core
from operations import execute
from init_project import init_project
from sprite_store import save_revision

PILLOW = importlib.util.find_spec("PIL") is not None


def seed(name="floor", foreground=False):
    return {"schema_version": 1, "name": name, "width": 8, "height": 8,
            "palette": {"a": "#78906a", "b": "#625457", "c": "#b0b7a0"},
            "pixels": ["b" * 8 if foreground else "a" * 8 for _ in range(8)]}


def source():
    return core.transitions(seed(), seed("wall", True), "walls", ["floor", "wall"], True)


class TileSchemaTests(unittest.TestCase):
    def test_generation_is_non_mutating_and_covers_both_centers_and_all_corners(self):
        a, b = seed(), seed("wall", True)
        before = copy.deepcopy((a, b))
        value = core.transitions(a, b, "walls", ["floor", "wall"], True)
        self.assertEqual((a, b), before)
        self.assertEqual(len(value["tiles"]), 162)
        report = core.seams(value)
        self.assertEqual(report["mismatch_count"], 0)
        self.assertEqual(report["layout_terrain_mismatches"], [])
        self.assertEqual(report["missing_corner_patterns"], [])
        self.assertEqual(report["missing_corner_pattern_count"], 0)
        self.assertTrue(report["visual_review_required"])
        self.assertEqual(sum(tile["solid"] for tile in value["tiles"]), 81)

    def test_incompatible_dimensions_palette_and_seed_edges_are_refused(self):
        for target in ("canvas", "palette", "edge"):
            value = seed("wall", True)
            if target == "canvas": value["pixels"] = [row[:-1] for row in value["pixels"]]; value["width"] = 7
            if target == "palette": value["palette"]["a"] = "#123456"
            if target == "edge": value["pixels"][2] = "abbbbbbb"
            with self.subTest(target=target), self.assertRaises(ValueError): core.transitions(seed(), value, "walls", ["floor", "wall"])

    def test_invalid_metadata_cells_bounds_and_duplicate_ids_are_refused(self):
        for target in ("terrain", "corners", "bool", "palette", "duplicate", "cell", "collision", "terrains"):
            value = source()
            if target == "terrain": value["tiles"][0]["terrain"] = True
            if target == "corners": value["tiles"][0]["corners"] = [0, 0, 0, 2]
            if target == "bool": value["tiles"][0]["solid"] = 1
            if target == "palette": value["tiles"][0]["source"]["palette"]["a"] = "#123456"
            if target == "duplicate": value["tiles"][0]["id"] = value["tiles"][1]["id"]
            if target == "cell": value["cells"].append(value["cells"][0])
            if target == "collision": value["collision_layer"] = -1
            if target == "terrains": value["terrains"] = [["floor"], "wall"]
            with self.subTest(target=target), self.assertRaises(ValueError): core.validate_source(value)

    def test_seam_metric_detects_pixels_and_layout_incompatibility(self):
        value = source()
        value["tiles"][0]["source"]["pixels"][0] = "caaaaaaa"
        self.assertGreater(core.seams(value)["mismatch_count"], 0)
        value["cells"] = [{"x": 0, "y": 0, "tile": "tile-0-00"}, {"x": 1, "y": 0, "tile": "tile-1-15"}]
        self.assertTrue(core.seams(value)["layout_terrain_mismatches"])


@unittest.skipUnless(PILLOW, "optional Pillow required for tileset rendering")
class TileWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Daydream tile fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        init_project(self.root, apply=True)
        self.files = core.make_revision(source(), {"method": "tileset-source", "license": None})
        self.bundle = self.root / "art/walls-v1"
        save_revision(self.bundle, self.files, True, kind=core.KIND)

    def call(self, name, data):
        result = execute(name, data, self.root)
        self.assertTrue(result["ok"], result)
        return result

    def approve(self):
        self.call("tileset.approve", {"bundle": "art/walls-v1", "revision_hash": sprite.digest(self.files["manifest.json"]), "reviewer": "synthetic fixture only", "apply": True})

    def test_inspect_preview_approve_import_and_collision_refusal(self):
        inspected = self.call("tileset.inspect", {"bundle": "art/walls-v1"})
        self.assertEqual(inspected["result"]["seams"]["mismatch_count"], 0)
        self.assertEqual(execute("tileset.import", {"bundle": "art/walls-v1"}, self.root)["status"], "needs_approval")
        self.approve()
        before = (self.root / ".daydream/assets.json").read_bytes()
        self.call("tileset.import", {"bundle": "art/walls-v1"})
        self.assertFalse((self.root / "assets").exists())
        self.assertEqual((self.root / ".daydream/assets.json").read_bytes(), before)
        self.call("tileset.import", {"bundle": "art/walls-v1", "apply": True})
        self.assertTrue((self.root / "assets/tilesets/walls.tileset.tres").is_file())
        self.assertTrue((self.root / "art/tilesets/walls.json").is_file())
        self.assertEqual(execute("tileset.import", {"bundle": "art/walls-v1", "apply": True}, self.root)["error"]["code"], "conflict")

    def test_native_preview_grants_and_cannot_approve(self):
        self.assertEqual(execute("tileset.approve", {}, self.root, surface="native")["error"]["code"], "unsupported")
        data = {"source": source(), "output": "art/native", "apply": True}
        self.assertEqual(execute("tileset.create", data, self.root, surface="native")["error"]["code"], "forbidden")
        preview = self.call("tileset.create", {**data, "apply": False})
        result = execute("tileset.create", data, self.root, surface="native", authorized=preview["access"])
        self.assertTrue(result["ok"], result)
        self.assertTrue((self.root / "art/native/atlas.png").is_file())

    def test_approved_bad_seams_still_cannot_import(self):
        value = source()
        value["tiles"][0]["source"]["pixels"][0] = "caaaaaaa"
        created = self.call("tileset.create", {"source": value, "output": "art/bad-seams", "apply": True})
        self.call("tileset.approve", {"bundle": "art/bad-seams", "revision_hash": created["result"]["revision_hash"], "reviewer": "synthetic negative test", "apply": True})
        result = execute("tileset.import", {"bundle": "art/bad-seams", "apply": True}, self.root)
        self.assertFalse(result["ok"])
        self.assertIn("mismatches", result["error"]["message"])
        self.assertFalse((self.root / "assets").exists())

    def test_reserved_godot_sidecar_is_preserved_and_blocks_import(self):
        self.approve()
        directory = self.root / "assets/tilesets"
        directory.mkdir(parents=True)
        sidecar = directory / "walls.layout.gd.uid"
        sidecar.write_text("user sidecar")
        before = (self.root / ".daydream/assets.json").read_bytes()
        result = execute("tileset.import", {"bundle": "art/walls-v1", "apply": True}, self.root)
        self.assertEqual(result["error"]["code"], "conflict")
        self.assertEqual(sidecar.read_text(), "user sidecar")
        self.assertFalse((directory / "walls.png").exists())
        self.assertEqual((self.root / ".daydream/assets.json").read_bytes(), before)

    def test_edit_preserves_source_and_requires_fresh_whole_revision_approval(self):
        self.approve()
        before = (self.bundle / "source.json").read_bytes()
        edited = self.call("tileset.edit", {"bundle": "art/walls-v1", "tiles": [{"id": "tile-1-15", "solid": False}], "output": "art/walls-v2", "apply": True})
        self.assertNotEqual(edited["result"]["revision_hash"], sprite.digest(self.files["manifest.json"]))
        self.assertEqual((self.bundle / "source.json").read_bytes(), before)
        self.assertFalse((self.root / "art/walls-v2/approval.json").exists())
        self.assertEqual(execute("tileset.import", {"bundle": "art/walls-v2"}, self.root)["status"], "needs_approval")

    def test_rehashed_wrong_pixels_report_and_old_approval_are_rejected(self):
        for name in ("preview.png", "seams.json"):
            with self.subTest(name=name):
                original = (self.bundle / name).read_bytes()
                (self.bundle / name).write_bytes(b'{}')
                manifest = json.loads(self.files["manifest.json"])
                manifest["files"][name] = sprite.digest(b'{}')
                (self.bundle / "manifest.json").write_bytes(sprite.encoded(manifest))
                with self.assertRaises((ValueError, OSError)): core.load_revision(self.bundle)
                (self.bundle / name).write_bytes(original)
                (self.bundle / "manifest.json").write_bytes(self.files["manifest.json"])
        self.approve()
        value = source(); value["collision_mask"] = 2
        changed = core.make_revision(value, {"method": "tileset-source", "license": None})
        for name, data in changed.items(): (self.bundle / name).write_bytes(data)
        self.assertEqual(execute("tileset.import", {"bundle": "art/walls-v1"}, self.root)["status"], "needs_approval")

    def test_transitions_operation_and_non_writing_cli(self):
        for name, foreground in (("floor", False), ("wall", True)):
            save_revision(self.root / ("art/" + name), sprite.make_revision(seed(name, foreground), {"method": "pixel-spec", "input_sha256": "0" * 64, "license": None}), True)
        data = {"background": "art/floor", "foreground": "art/wall", "name": "terrain", "terrains": ["floor", "wall"], "output": "art/generated", "solid_foreground": True}
        preview = self.call("tileset.transitions", data)
        self.assertEqual(preview["status"], "preview")
        self.assertFalse((self.root / "art/generated").exists())
        self.call("tileset.transitions", {**data, "apply": True})
        self.assertEqual(len(core.load_revision(self.root / "art/generated")["source"]["tiles"]), 162)
        result = subprocess.run([sys.executable, str(ROOT / "scripts/operations.py"), "--project", str(self.root), "describe", "tileset.transitions"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "set GODOT_BIN for isolated real TileSet checks")
    def test_real_godot_atlas_terrain_autotiling_collision_and_layout(self):
        self.approve()
        self.call("tileset.import", {"bundle": "art/walls-v1", "apply": True})
        (self.root / "check.gd").write_text('''extends SceneTree
func _initialize():
    call_deferred("check")
func check():
    var tiles = load("res://assets/tilesets/walls.tileset.tres") as TileSet
    assert(tiles != null)
    assert(tiles.tile_size == Vector2i(8, 8))
    assert(tiles.get_terrain_sets_count() == 1)
    assert(tiles.get_terrain_set_mode(0) == TileSet.TERRAIN_MODE_MATCH_CORNERS)
    assert(tiles.get_terrains_count(0) == 2)
    assert(tiles.get_physics_layer_collision_layer(0) == 1)
    var atlas = tiles.get_source(0) as TileSetAtlasSource
    assert(atlas.get_tiles_count() == 162)
    var floor_tile = atlas.get_tile_data(Vector2i(0, 0), 0)
    assert(floor_tile.terrain == 0)
    assert(floor_tile.get_collision_polygons_count(0) == 0)
    var wall_tile = atlas.get_tile_data(Vector2i(7, 3), 0)
    assert(wall_tile.terrain == 1)
    assert(wall_tile.get_collision_polygons_count(0) == 1)
    assert(wall_tile.get_collision_polygon_points(0, 0).size() == 4)
    assert(wall_tile.get_terrain_peering_bit(TileSet.CELL_NEIGHBOR_TOP_LEFT_CORNER) == 1)
    var layer = load("res://assets/tilesets/walls.tscn").instantiate() as TileMapLayer
    root.add_child(layer)
    assert(layer.get_used_cells().size() == 25)
    assert(layer.texture_filter == CanvasItem.TEXTURE_FILTER_NEAREST)
    await process_frame
    var cells: Array[Vector2i] = [Vector2i(10, 10), Vector2i(11, 10), Vector2i(10, 11), Vector2i(11, 11)]
    layer.set_cells_terrain_connect(cells, 0, 1)
    for cell in cells:
        assert(layer.get_cell_source_id(cell) == 0)
        assert(layer.get_cell_tile_data(cell).terrain == 1)
    layer.set_cell(Vector2i(20, 20), 0, Vector2i(7, 3))
    layer.update_internals()
    await physics_frame
    await physics_frame
    var query = PhysicsRayQueryParameters2D.create(Vector2(164, 150), Vector2(164, 180), 1)
    var hit = layer.get_world_2d().direct_space_state.intersect_ray(query)
    assert(not hit.is_empty())
    assert(hit["collider"] == layer)
    print("DAYDREAM_TILESET_OK")
    quit()
''')
        godot = os.environ["GODOT_BIN"]
        for args in (["--headless", "--editor", "--import"], ["--headless", "--script", "res://check.gd"]):
            try:
                result = subprocess.run([godot, "--path", str(self.root), *args], capture_output=True, text=True, timeout=15)
            except subprocess.TimeoutExpired as exc:
                self.fail(f"Godot fixture timed out: {exc.stdout!r}\n{exc.stderr!r}")
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn("ERROR:", output)
        self.assertIn("DAYDREAM_TILESET_OK", output)
