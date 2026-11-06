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
import collision_core as collision
import sprite_core as sprite
import tileset_core as tileset
from operations import execute

PILLOW = importlib.util.find_spec("PIL") is not None


def source():
    seed = {"schema_version": 1, "name": "ground", "width": 16, "height": 16,
            "palette": {"a": "#73967a", "b": "#394655"}, "pixels": ["a" * 16] * 16}
    tiles = []
    for name, preset in (("right", "slope_up_right"), ("left", "slope_up_left"), ("multi", "none"), ("platform", "platform"), ("empty", "none"), ("legacy", "full")):
        tile = {"id": name, "source": copy.deepcopy(seed), "solid": False, "terrain": 0, "corners": [0, 0, 0, 0]}
        if name == "legacy":
            tile["solid"] = True
        else:
            options = {"preset": preset}
            if name == "platform": options.update({"thickness": 2, "one_way_margin": .75})
            tile["collisions"] = collision.from_preset(options, 16, 16)
        if name == "multi":
            tile["collisions"] = [{"points": [[0, .5], [4, 0], [4, 16], [0, 16]]}, {"points": [[12, 0], [16, 0], [16, 16], [12, 16]]}]
        tiles.append(tile)
    cells = [{"x": index*2, "y": 2 if tile["id"] == "platform" else 0, "tile": tile["id"]} for index, tile in enumerate(tiles)]
    return {"schema_version": 1, "name": "geometry", "terrains": ["ground"], "tiles": tiles, "cells": cells, "collision_layer": 1, "collision_mask": 1}


class CollisionSchemaTests(unittest.TestCase):
    def test_presets_convex_pieces_and_half_pixel_points_are_explicit(self):
        value = tileset.validate_source(source())
        self.assertEqual(collision.summary(value)["polygon_count"], 6)
        self.assertEqual(collision.summary(value)["one_way_polygons"], 1)
        self.assertEqual(collision.summary(value)["explicit_tiles"], 5)
        self.assertFalse(collision.summary(value)["inferred_from_alpha"])
        points = [{"points": [[0, .5], [16, .5], [16, 2], [0, 2]], "one_way": True, "one_way_margin": .5}]
        before = copy.deepcopy(points)
        self.assertEqual(collision.validate_polygons(points, 16, 16), points)
        self.assertEqual(points, before)
        reversed_points = [{"points": list(reversed(points[0]["points"]))}]
        collision.validate_polygons(reversed_points, 16, 16)

    def test_invalid_geometry_and_settings_are_rejected(self):
        invalid = [
            [[0, 0], [8, 8], [0, 8], [8, 0]],  # self intersection
            [[0, 0], [8, 0], [4, 4], [8, 8], [0, 8]],  # concave
            [[0, 0], [4, 0], [8, 0]],  # zero area
            [[0, 0], [8, 0], [8, 8], [0, 0]],  # repeated closing vertex
            [[-1, 0], [8, 0], [8, 8]],
            [[0, 0], [17, 0], [8, 8]],
            [[True, 0], [8, 0], [8, 8]],
            [[float("nan"), 0], [8, 0], [8, 8]],
            [[float("inf"), 0], [8, 0], [8, 8]],
            [[.25, 0], [8, 0], [8, 8]],
            [[0, 0], [8, 0]],
        ]
        for points in invalid:
            with self.subTest(points=points), self.assertRaises(ValueError): collision.validate_polygons([{"points": points}], 16, 16)
        for extra in ({"one_way": 1}, {"one_way_margin": -1}, {"one_way_margin": True}, {"one_way_margin": float("inf")}, {"arbitrary": 1}):
            with self.subTest(extra=extra), self.assertRaises(ValueError): collision.validate_polygons([{"points": [[0, 0], [8, 0], [8, 8]], **extra}], 16, 16)
        with self.assertRaises(ValueError): collision.validate_polygons([{"points": [[0, 0], [8, 0], [8, 8]]}] * 9, 16, 16)
        for options in ({"preset": "bad"}, {"preset": "none", "one_way": True}, {"preset": "full", "thickness": 1}, {"preset": "platform", "thickness": 17}):
            with self.subTest(options=options), self.assertRaises(ValueError): collision.from_preset(options, 16, 16)

    def test_legacy_and_explicit_geometry_do_not_mix_silently(self):
        legacy = source()["tiles"][-1]
        self.assertEqual(len(collision.effective_polygons(legacy)), 1)
        before = copy.deepcopy(legacy)
        collision.edit_collision(legacy, {"collision_preset": {"preset": "slope_up_right"}})
        self.assertFalse(legacy["solid"])
        self.assertIn("collisions", legacy)
        collision.edit_collision(legacy, {"solid": True})
        self.assertEqual(legacy, before)
        with self.assertRaises(ValueError): collision.edit_collision(legacy, {"solid": True, "collisions": []})
        value = source(); value["tiles"][0]["solid"] = True
        with self.assertRaises(ValueError): tileset.validate_source(value)


@unittest.skipUnless(PILLOW, "optional Pillow required")
class CollisionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Collision fixture"\n[rendering]\nrenderer/rendering_method="gl_compatibility"\n')
        self.call("project.init", {"apply": True})

    def call(self, name, data, **kwargs):
        result = execute(name, data, self.root, **kwargs)
        self.assertTrue(result["ok"], result)
        return result

    def create(self):
        return self.call("tileset.create", {"source": source(), "output": "art/geometry-v1", "apply": True})

    def approve(self, bundle="art/geometry-v1"):
        revision = tileset.load_revision(self.root / bundle)
        self.call("tileset.approve", {"bundle": bundle, "revision_hash": revision["revision_hash"], "reviewer": "synthetic geometry test", "apply": True})

    def test_overlay_source_and_approval_are_bound_without_modifying_legacy(self):
        value = source()
        legacy = copy.deepcopy(value)
        for tile in legacy["tiles"]: tile.pop("collisions", None)
        original = copy.deepcopy(legacy)
        created = self.call("tileset.create", {"source": legacy, "output": "art/legacy", "apply": True})
        self.assertEqual(tileset.load_revision(self.root / "art/legacy")["source"], original)
        self.assertFalse((self.root / "art/legacy/collisions.png").exists())
        viewer = (self.root / "art/legacy/preview.html").read_text()
        self.assertIn("Yellow outlines indicate full-tile collisions.", viewer)
        self.approve("art/legacy")
        self.call("tileset.edit", {"bundle": "art/legacy", "tiles": [{"id": "right", "collision_preset": {"preset": "slope_up_right"}}], "output": "art/new", "apply": True})
        inspected = self.call("tileset.inspect", {"bundle": "art/new"})["result"]
        self.assertIn("collision_preview", inspected)
        self.assertEqual(inspected["collisions"]["explicit_tiles"], 1)
        self.assertTrue((self.root / "art/new/collisions.png").exists())
        self.assertFalse((self.root / "art/new/approval.json").exists())
        self.assertEqual(tileset.load_revision(self.root / "art/legacy")["revision_hash"], created["result"]["revision_hash"])
        self.assertEqual(execute("tileset.import", {"bundle": "art/new"}, self.root)["status"], "needs_approval")

    def test_custom_geometry_survives_native_grants_and_tampered_overlay_is_rejected(self):
        data = {"source": source(), "output": "art/native"}
        preview = self.call("tileset.create", data)
        self.assertFalse((self.root / "art/native").exists())
        self.call("tileset.create", {**data, "apply": True}, surface="native", authorized=preview["access"])
        revision = tileset.load_revision(self.root / "art/native")
        self.assertIn("collisions.png", revision["manifest"]["files"])
        manifest = revision["manifest"]
        # Even a self-consistent hash edit cannot make a wrong overlay depict the source.
        wrong = (self.root / "art/native/layout.png").read_bytes()
        (self.root / "art/native/collisions.png").write_bytes(wrong)
        manifest["files"]["collisions.png"] = sprite.digest(wrong)
        (self.root / "art/native/manifest.json").write_bytes(sprite.encoded(manifest))
        with self.assertRaisesRegex(ValueError, "image does not match"): tileset.load_revision(self.root / "art/native")

    def test_editing_only_one_way_or_margin_requires_a_fresh_review(self):
        self.create(); self.approve()
        changed = self.call("tileset.edit", {"bundle": "art/geometry-v1", "tiles": [{"id": "platform", "collision_preset": {"preset": "platform", "one_way_margin": 2}}], "output": "art/geometry-v2", "apply": True})
        self.assertNotEqual(changed["result"]["revision_hash"], tileset.load_revision(self.root / "art/geometry-v1")["revision_hash"])
        self.assertEqual(self.call("review.inspect", {"kind": "tileset", "bundle": "art/geometry-v2"})["result"]["state"], "unreviewed")

    @unittest.skipUnless(os.environ.get("GODOT_BIN"), "set GODOT_BIN for real collision physics")
    def test_real_godot_polygon_normals_gaps_and_one_way_movement(self):
        self.create(); self.approve()
        self.call("tileset.import", {"bundle": "art/geometry-v1", "apply": True})
        (self.root / "check.gd").write_text('''extends SceneTree
func _initialize():
    call_deferred("check")
func ray(layer, x):
    return layer.get_world_2d().direct_space_state.intersect_ray(PhysicsRayQueryParameters2D.create(Vector2(x, -8), Vector2(x, 24), 1))
func check():
    var layer = load("res://assets/tilesets/geometry.tscn").instantiate() as TileMapLayer
    root.add_child(layer)
    var atlas = layer.tile_set.get_source(0) as TileSetAtlasSource
    assert(atlas.get_tile_data(Vector2i(0, 0), 0).get_collision_polygon_points(0, 0).size() == 3)
    assert(atlas.get_tile_data(Vector2i(2, 0), 0).get_collision_polygons_count(0) == 2)
    assert(atlas.get_tile_data(Vector2i(2, 0), 0).get_collision_polygon_points(0, 0)[0] == Vector2(-8, -7.5))
    var platform = atlas.get_tile_data(Vector2i(3, 0), 0)
    assert(platform.is_collision_polygon_one_way(0, 0))
    assert(is_equal_approx(platform.get_collision_polygon_one_way_margin(0, 0), 0.75))
    assert(atlas.get_tile_data(Vector2i(4, 0), 0).get_collision_polygons_count(0) == 0)
    layer.update_internals()
    await physics_frame
    await physics_frame
    var right = ray(layer, 4)
    assert(not right.is_empty())
    assert(abs(right.position.y - 12) < 0.1)
    assert(right.normal.x < -0.6 and right.normal.y < -0.6)
    assert(abs(ray(layer, 12).position.y - 4) < 0.1)
    var left = ray(layer, 36)
    assert(abs(left.position.y - 4) < 0.1)
    assert(left.normal.x > 0.6 and left.normal.y < -0.6)
    assert(not ray(layer, 66).is_empty())
    assert(ray(layer, 72).is_empty())
    assert(not ray(layer, 78).is_empty())
    assert(ray(layer, 136).is_empty())
    assert(not ray(layer, 168).is_empty())
    var actor = CharacterBody2D.new()
    var shape = CollisionShape2D.new()
    var rectangle = RectangleShape2D.new()
    rectangle.size = Vector2(2, 2)
    shape.shape = rectangle
    actor.add_child(shape)
    actor.position = Vector2(104, 42)
    root.add_child(actor)
    for i in range(30):
        await physics_frame
        actor.velocity = Vector2(0, -100)
        actor.move_and_slide()
    assert(actor.position.y < 30) # Pass upward through the platform.
    actor.position = Vector2(104, 20)
    for i in range(30):
        await physics_frame
        actor.velocity = Vector2(0, 80)
        actor.move_and_slide()
    assert(abs(actor.position.y - 31) < 0.2) # Land on its top surface.
    assert(actor.is_on_floor())
    print("DAYDREAM_COLLISION_PHYSICS_OK")
    quit()
''')
        for args in (["--headless", "--editor", "--import"], ["--headless", "--max-fps", "60", "--script", "res://check.gd", "--quit-after", "240"]):
            result = subprocess.run([os.environ["GODOT_BIN"], "--path", str(self.root), *args], capture_output=True, text=True, timeout=30)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn("ERROR:", output)
        self.assertIn("DAYDREAM_COLLISION_PHYSICS_OK", output)
