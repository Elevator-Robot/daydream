import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from operations import execute
from editor_layout import stable_identifiers, run_engine
from operation_registry import find
from test_collisions import source
from engine_selection import project_engine
from operations import Context


class SerializationBoundaryTests(unittest.TestCase):
    def test_project_settings_and_path_discovery_need_no_executable_or_version_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'project.godot').write_text('config_version=5\n[application]\nconfig/features=PackedStringArray("4.7", "GL Compatibility")\n')
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch('engine_selection.shutil.which', return_value=sys.executable):
                selected = project_engine(Context(root), {})
            self.assertEqual(selected['godot'], str(Path(sys.executable).resolve()))
            self.assertEqual(selected['expected_version'], '4.7')
            self.assertEqual(selected['selection'], 'PATH')

    def test_explicit_project_engine_pin_wins_and_conflicts_are_not_ignored(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); (root/'.daydream').mkdir()
            (root/'project.godot').write_text('[application]\nconfig/features=PackedStringArray("4.7", "GL Compatibility")\n')
            (root/'.daydream/preview.json').write_text(json.dumps({'godot': sys.executable, 'version': '4.7.2'}))
            selected = project_engine(Context(root), {})
            self.assertEqual(selected['selection'], 'project settings')
            self.assertEqual(selected['expected_version'], '4.7.2')
            with self.assertRaisesRegex(ValueError, 'conflicts'):
                project_engine(Context(root), {'godot_version': '4.6.3'})
            (root/'.daydream/preview.json').write_text(json.dumps({'godot': sys.executable, 'version': '4.6.3'}))
            with self.assertRaisesRegex(ValueError, 'conflict'):
                project_engine(Context(root), {})

    def test_missing_godot_has_actionable_setup_error_without_installing(self):
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {}, clear=True), mock.patch('engine_selection.shutil.which', return_value=None):
                with self.assertRaisesRegex(ValueError, "Godot wasn't found"):
                    project_engine(Context(temporary), {})

    def test_engine_resolution_requires_read_grants_but_never_execution(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root/'project.godot').write_text('[application]\nconfig/features=PackedStringArray("4.7")\n')
            data = {'bundle': 'art/tiles', 'godot': sys.executable}
            prepared = execute('tileset.editor_import', data, root, surface='native', prepare_only=True)
            self.assertTrue(prepared['access']['engine_resolution'])
            with mock.patch('editor_layout.run_engine') as engine:
                denied = execute('tileset.editor_import', data, root, surface='native', resolve_only=True)
                self.assertEqual(denied['error']['code'], 'forbidden')
                resolved = execute('tileset.editor_import', data, root, surface='native', resolve_only=True, authorized={'reads': prepared['access']['reads'], 'writes': []})
                self.assertTrue(resolved['ok'], resolved)
                self.assertEqual(resolved['engine']['expected_version'], '4.7')
                engine.assert_not_called()

    def test_normalization_changes_only_documented_scene_local_labels(self):
        scene = b'[gd_scene format=4]\n\n[ext_resource type="TileSet" path="res://assets/a.tileset.tres" id="1_random"]\n\n[node name="a" type="TileMapLayer" unique_id=123]\ntile_map_data = PackedByteArray("AQID")\ntile_set = ExtResource("1_random")\n'
        normalized = stable_identifiers(scene, "a", "assets/a.tileset.tres")
        self.assertIn(b'PackedByteArray("AQID")', normalized)
        self.assertIn(b'unique_id=1]', normalized)
        self.assertNotIn(b'1_random', normalized)
        with self.assertRaises(ValueError): stable_identifiers(scene.replace(b'TileMapLayer', b'Node2D'), "a", "assets/a.tileset.tres")
        with self.assertRaises(ValueError): stable_identifiers(scene + b'[node name="extra" type="Node"]\n', "a", "assets/a.tileset.tres")

    def test_missing_execution_grant_blocks_handler_before_any_engine_call(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = {"bundle": "art/tiles", "godot": sys.executable, "godot_version": "4.7.2"}
            prepared = execute("tileset.editor_import", data, root, surface="native", prepare_only=True)
            self.assertTrue(prepared["ok"], prepared)
            grants = {"reads": prepared["access"]["reads"], "writes": []}
            with mock.patch('operation_handlers.tileset_editor_import') as called:
                # The canonical registration holds the original handler; guard
                # the lower library too so no accidental invocation is hidden.
                with mock.patch('editor_layout.run_engine') as engine:
                    result = execute("tileset.editor_import", data, root, surface="native", authorized=grants)
                    self.assertEqual(result["error"]["code"], "forbidden")
                    engine.assert_not_called()
                called.assert_not_called()
            self.assertEqual(list(root.iterdir()), [])

    def test_owned_process_timeout_and_output_limit_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary:
            env = dict(os.environ)
            with self.assertRaisesRegex(ValueError, "timed out"):
                run_engine(sys.executable, ['-c', 'import time; time.sleep(30)'], temporary, env, .2)
            with self.assertRaisesRegex(ValueError, "output limit"):
                run_engine(sys.executable, ['-c', 'print("x" * 10000)'], temporary, env, 2, 100)


@unittest.skipUnless(importlib.util.find_spec("PIL") and os.environ.get("GODOT_BIN"), "optional Pillow and GODOT_BIN required")
class EditorLayoutGodotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # This deliberately invalid target autoload would fail if the serializer
        # ever opened the target game rather than its own generated fixture.
        (self.root / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="Editor layout fixture"\n[autoload]\nDoNotExecute="*res://should-never-run.gd"\n')
        self.call('project.init', {"apply": True})
        created = self.call('tileset.create', {"source": source(), "output": "art/tiles", "apply": True})
        self.hash = created['result']['revision_hash']
        self.call('tileset.approve', {"bundle": "art/tiles", "revision_hash": self.hash, "reviewer": "synthetic editor fixture", "apply": True})
        self.godot = str(Path(os.environ['GODOT_BIN']).resolve())
        version = subprocess.check_output([self.godot, '--version'], text=True, timeout=5).strip()
        self.version = re.match(r'4\.\d+\.\d+', version)[0]
        self.data = {"bundle": "art/tiles", "godot": self.godot, "godot_version": self.version, "revision_hash": self.hash}

    def call(self, op, data, **kwargs):
        result = execute(op, data, self.root, **kwargs)
        self.assertTrue(result['ok'], result)
        return result

    def test_plan_is_deterministic_and_apply_uses_exact_script_free_bytes(self):
        first = self.call('tileset.editor_import', self.data)
        second = self.call('tileset.editor_import', self.data)
        self.assertEqual(first['result']['plan_hash'], second['result']['plan_hash'])
        self.assertFalse((self.root / 'assets').exists())
        self.assertFalse((self.root / '.godot').exists())
        self.assertTrue(first['evidence']['godot_run'])
        self.assertFalse(first['result']['serialization']['game_project_executed'])
        self.assertFalse(first['result']['serialization']['script_attached'])
        self.assertFalse(any(path.endswith('.gd') for path in first['result']['create']))
        result = self.call('tileset.editor_import', {**self.data, 'plan_hash': first['result']['plan_hash'], 'apply': True},
                           surface='native', authorized=first['access'])
        self.assertEqual(result['result']['plan_hash'], first['result']['plan_hash'])
        scene = self.root / 'assets/tilesets/geometry.tscn'
        text = scene.read_text()
        self.assertIn('tile_map_data', text)
        self.assertNotIn('script =', text)
        self.assertNotIn('res://_daydream_', text)
        # Preserve an explicitly manual edit, including its original index entry.
        scene.write_text(text + '\n; manually edited\n')
        index = (self.root / '.daydream/assets.json').read_bytes()
        blocked = execute('tileset.editor_import', {**self.data, 'apply': True}, self.root)
        self.assertEqual(blocked['error']['code'], 'conflict')
        self.assertTrue(scene.read_text().endswith('; manually edited\n'))
        self.assertEqual((self.root / '.daydream/assets.json').read_bytes(), index)

    def test_version_and_stale_plan_refusal_leave_outputs_unwritten(self):
        bad = execute('tileset.editor_import', {**self.data, 'godot_version': '4.3.99'}, self.root)
        self.assertFalse(bad['ok'])
        self.assertIn('version mismatch', bad['error']['message'])
        bad = execute('tileset.editor_import', {**self.data, 'plan_hash': '0' * 64, 'apply': True}, self.root)
        self.assertFalse(bad['ok'])
        self.assertIn('plan changed', bad['error']['message'])
        self.assertFalse((self.root / 'assets').exists())
        self.assertFalse((self.root / '.godot').exists())

    def test_auto_detected_engine_and_project_target_import_without_manual_fields(self):
        target = '.'.join(self.version.split('.')[:2])
        (self.root/'project.godot').write_text('[application]\nconfig/features=PackedStringArray("' + target + '", "GL Compatibility")\n')
        with mock.patch.dict(os.environ, {'GODOT_BIN': ''}), mock.patch('engine_selection.shutil.which', return_value=self.godot):
            preview = self.call('tileset.editor_import', {'bundle': 'art/tiles'})
            self.assertEqual(preview['result']['serialization']['selection'], 'PATH')
            self.assertEqual(preview['result']['serialization']['project_target'], target)
            self.call('tileset.editor_import', {'bundle': 'art/tiles', 'apply': True, 'plan_hash': preview['result']['plan_hash']}, surface='native', authorized=preview['access'])
        self.assertTrue((self.root/'assets/tilesets/geometry.tscn').exists())
        self.assertFalse((self.root/'.daydream/preview.json').exists())

    def test_cells_exist_before_ready_and_manual_save_reload_is_not_reset(self):
        self.call('tileset.editor_import', {**self.data, 'apply': True})
        # Only this explicit fixture verification opens the target. The product
        # serializer did not execute its deliberately invalid autoload above.
        (self.root / 'project.godot').write_text('config_version=5\n[application]\nconfig/name="Manual edit fixture"\n')
        (self.root / 'verify.gd').write_text('''extends SceneTree
func _initialize():
    call_deferred("check")
func check():
    var packed = load("res://assets/tilesets/geometry.tscn") as PackedScene
    var layer = packed.instantiate() as TileMapLayer
    assert(not layer.is_inside_tree())
    assert(layer.get_script() == null)
    assert(layer.get_used_cells().size() == 6)
    assert(layer.get_meta("daydream_layout_mode") == "editor")
    assert(layer.get_cell_tile_data(Vector2i(6, 2)).is_collision_polygon_one_way(0, 0))
    layer.erase_cell(Vector2i(0, 0))
    layer.set_cell(Vector2i(12, 3), 0, Vector2i(1, 0))
    var saved = PackedScene.new()
    assert(saved.pack(layer) == OK)
    assert(ResourceSaver.save(saved, "res://edited.tscn") == OK)
    layer.free()
    var reloaded = ResourceLoader.load("res://edited.tscn", "PackedScene", ResourceLoader.CACHE_MODE_IGNORE).instantiate() as TileMapLayer
    assert(reloaded.get_script() == null)
    assert(reloaded.get_cell_source_id(Vector2i(0, 0)) == -1)
    assert(reloaded.get_cell_atlas_coords(Vector2i(12, 3)) == Vector2i(1, 0))
    root.add_child(reloaded)
    await process_frame
    assert(reloaded.get_cell_source_id(Vector2i(0, 0)) == -1)
    assert(reloaded.get_cell_atlas_coords(Vector2i(12, 3)) == Vector2i(1, 0))
    print("DAYDREAM_EDITOR_CELLS_PERSIST")
    quit()
''')
        for args in (["--headless", "--editor", "--import"], ["--headless", "--script", "res://verify.gd", "--quit-after", "120"]):
            result = subprocess.run([self.godot, '--path', str(self.root), *args], text=True, capture_output=True, timeout=30)
            output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, output)
            self.assertNotIn('ERROR:', output)
        self.assertIn('DAYDREAM_EDITOR_CELLS_PERSIST', output)
