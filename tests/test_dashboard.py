import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from operations import execute
from review_fixture import create


@unittest.skipUnless(importlib.util.find_spec('PIL'), 'optional Pillow required')
class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundles = create(self.root)

    def call(self, op, data, **kwargs):
        result = execute(op, data, self.root, **kwargs)
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['access']['writes'], [])
        return result

    def image(self, path='assets/existing.png'):
        from PIL import Image
        file = self.root / path
        file.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGBA', (640, 360), '#aabbcc').save(file)
        return file

    def test_collection_includes_existing_art_and_separate_latest_history(self):
        self.image()
        self.image('.godot/ignored.png')
        self.image('node_modules/ignored.png')
        (self.root / 'assets/linked.png').symlink_to('/etc/passwd')
        result = execute('sprite.edit', {'bundle': 'art/dot', 'patch': {'schema_version': 1, 'operations': [{'op': 'recolor', 'symbol': 'a', 'color': '#123456'}]}, 'apply': True}, self.root)
        self.assertTrue(result['ok'], result)
        catalog = self.call('dashboard.catalog', {})['result']
        self.assertEqual(len(catalog['assets']), 5)
        self.assertEqual(sum(item['is_latest'] for item in catalog['assets']), 4)
        existing = next(item for item in catalog['assets'] if item['origin'] == 'project')
        self.assertEqual(existing['path'], 'assets/existing.png')
        self.assertEqual(existing['state'], 'project_file')
        self.assertEqual(catalog['project']['directory'], str(self.root))
        self.assertFalse(catalog['truncated'])

    def test_inspect_and_media_preserve_sources_for_all_kinds(self):
        self.image()
        for kind, path in [*self.bundles.items(), ('image', 'assets/existing.png')]:
            with self.subTest(kind=kind):
                files = [self.root / path] if kind == 'image' else list((self.root / path).iterdir())
                before = {file: file.read_bytes() for file in files}
                inspected = self.call('dashboard.inspect', {'path': path, 'kind': kind})['result']
                self.assertEqual(inspected['kind'], kind)
                media = self.call('dashboard.media', {'path': path, 'kind': kind, 'image': 'thumbnail', 'revision_hash': inspected['revision_hash']})['result']
                self.assertLessEqual(media['width'], 256)
                self.assertLessEqual(media['height'], 192)
                self.assertEqual(media['mime'], 'image/png')
                self.assertEqual({file: file.read_bytes() for file in files}, before)
                if kind == 'animation':
                    self.assertTrue(inspected['animations'][0]['loop'])
                    self.assertEqual(inspected['frames'][0]['index'], 0)
                if kind == 'tileset':
                    self.assertEqual(inspected['tiles'][0]['id'], 'floor')
                    self.assertEqual(inspected['terrains'], ['floor'])
                    self.assertEqual(inspected['cells'][0]['tile'], 'floor')

    def test_permission_resolution_and_exact_media_grants(self):
        self.image()
        prepared = execute('dashboard.catalog', {}, self.root, surface='native', prepare_only=True)
        grants = {'reads': prepared['access']['reads'], 'writes': []}
        denied = execute('dashboard.catalog', {}, self.root, surface='native', authorized=grants)
        self.assertEqual(denied['error']['code'], 'forbidden')
        resolved = self.call('dashboard.catalog', {}, surface='native', resolve_only=True, authorized=grants)
        self.call('dashboard.catalog', {}, surface='native', authorized=resolved['access'])
        denied = execute('dashboard.media', {'kind': 'image', 'path': 'assets/existing.png'}, self.root, surface='native', authorized={'reads': [], 'writes': []})
        self.assertEqual(denied['error']['code'], 'forbidden')

    def test_refresh_finds_new_files_and_stale_or_corrupt_media_is_refused(self):
        first = self.call('dashboard.catalog', {})['result']
        file = self.image()
        second = self.call('dashboard.catalog', {})['result']
        self.assertEqual(len(second['assets']), len(first['assets']) + 1)
        inspected = self.call('dashboard.inspect', {'kind': 'image', 'path': 'assets/existing.png'})['result']
        from PIL import Image
        Image.new('RGBA', (10, 10), 'red').save(file)
        stale = execute('dashboard.media', {'kind': 'image', 'path': 'assets/existing.png', 'revision_hash': inspected['revision_hash']}, self.root)
        self.assertFalse(stale['ok'])
        self.assertIn('changed', stale['error']['message'])
        (self.root / 'art/dot/sprite.png').write_bytes(b'corrupt')
        self.assertFalse(execute('dashboard.media', {'kind': 'sprite', 'path': 'art/dot'}, self.root)['ok'])
        self.assertFalse(execute('dashboard.media', {'kind': 'image', 'path': '../escape.png'}, self.root)['ok'])
        self.assertFalse(execute('dashboard.media', {'kind': 'animation', 'path': 'art/walk', 'image': '../source.json'}, self.root)['ok'])

    def test_discovery_limit_is_visible_and_svg_is_never_executed(self):
        self.image('assets/one.png'); self.image('assets/two.png')
        with mock.patch('dashboard.MAX_FILES', 1):
            catalog = self.call('dashboard.catalog', {})['result']
            self.assertTrue(catalog['truncated'])
        (self.root / 'assets/icon.svg').write_text('<svg onload="alert(1)"><script>throw 1</script></svg>')
        catalog = self.call('dashboard.catalog', {})['result']
        self.assertTrue(any(item['path'] == 'assets/icon.svg' for item in catalog['assets']))
        result = execute('dashboard.media', {'kind': 'image', 'path': 'assets/icon.svg'}, self.root)
        self.assertFalse(result['ok'])
        self.assertIn('SVG', result['error']['message'])

    def test_sprite_animation_relationship_survives_edit_and_does_not_guess_names(self):
        # review_fixture assembles "walk" from "dot": names intentionally differ.
        edited = execute('animation.edit', {'bundle': 'art/walk', 'patch': {'schema_version': 1, 'operations': [{'op': 'recolor', 'symbol': 'a', 'color': '#667788'}]}, 'apply': True}, self.root)
        self.assertTrue(edited['ok'], edited)
        catalog = self.call('dashboard.catalog', {})['result']
        sprite = next(item for item in catalog['assets'] if item['kind'] == 'sprite')
        animations = [item for item in catalog['assets'] if item['kind'] == 'animation']
        self.assertEqual(len(animations), 2)
        self.assertTrue(all(item['sprite_groups'] == [sprite['group']] for item in animations))

    def test_existing_tileset_atlases_are_discovered_from_resources_and_folders(self):
        self.image('assets/ordinary-sheet.png')
        self.image('assets/tilesets/folder-atlas.png')
        self.image('assets/unrelated.png')
        (self.root / 'main.tscn').write_text('[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://assets/ordinary-sheet.png" id="tile_art"]\n[sub_resource type="TileSetAtlasSource" id="atlas"]\ntexture = ExtResource("tile_art")\n0:0/0 = 0\n')
        catalog = self.call('dashboard.catalog', {})['result']
        existing = {item['path']: item for item in catalog['assets'] if item['origin'] == 'project'}
        self.assertEqual(existing['assets/ordinary-sheet.png']['collection_type'], 'tileset')
        self.assertEqual(existing['assets/ordinary-sheet.png']['resource_references'], ['main.tscn'])
        self.assertEqual(existing['assets/ordinary-sheet.png']['tileset_evidence'], 'godot_reference')
        self.assertEqual(existing['assets/tilesets/folder-atlas.png']['tileset_evidence'], 'folder')
        self.assertEqual(existing['assets/unrelated.png']['collection_type'], 'image')
        detail = self.call('dashboard.inspect', {'path': 'assets/ordinary-sheet.png', 'kind': 'image'})['result']
        self.assertNotIn('tiles', detail)  # No guessed tile size, terrain or collision metadata.

    def test_tileset_reference_discovery_respects_exact_resource_read_grants(self):
        self.image('atlas.png')
        (self.root / 'atlas.tres').write_text('[gd_resource type="TileSetAtlasSource" format=3]\n[ext_resource type="Texture2D" path="res://atlas.png" id="1"]\n[resource]\ntexture = ExtResource("1")\n')
        prepared = execute('dashboard.catalog', {}, self.root, surface='native', prepare_only=True)
        resolved = self.call('dashboard.catalog', {}, surface='native', resolve_only=True, authorized={'reads': prepared['access']['reads'], 'writes': []})
        resource = str(self.root / 'atlas.tres')
        self.assertIn(resource, resolved['access']['reads'])
        incomplete = {'reads': [file for file in resolved['access']['reads'] if file != resource], 'writes': []}
        self.assertEqual(execute('dashboard.catalog', {}, self.root, surface='native', authorized=incomplete)['error']['code'], 'forbidden')

    def test_existing_sprite2d_images_are_sprites_without_becoming_managed_candidates(self):
        image = self.image('textures/hero.png')
        before = image.read_bytes()
        (self.root / 'hero.tscn').write_text('[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://textures/hero.png" id="art"]\n[node name="Hero" type="Sprite2D"]\ntexture = ExtResource("art")\n')
        asset = next(item for item in self.call('dashboard.catalog', {})['result']['assets'] if item['path'] == 'textures/hero.png')
        self.assertEqual(asset['collection_type'], 'sprite')
        self.assertEqual(asset['sprite_evidence'], 'godot_reference')
        self.assertEqual(asset['resource_references'], ['hero.tscn'])
        self.assertEqual(asset['kind'], 'image')  # Still uses bounded project-image reads, not a bundle loader.
        self.assertEqual(asset['state'], 'project_file')
        self.assertEqual(image.read_bytes(), before)

    def test_embedded_spriteframes_atlas_references_classify_wonderer_style_sheets(self):
        self.image('textures/hero-sheet.png')
        (self.root / 'player.tscn').write_text('''[gd_scene format=3]
[ext_resource type="Texture2D" path="res://textures/hero-sheet.png" id="sheet"]
[sub_resource type="AtlasTexture" id="frame0"]
atlas = ExtResource("sheet")
region = Rect2(0, 0, 96, 96)
[sub_resource type="SpriteFrames" id="motion"]
animations = [{
"frames": [{"duration": 1.0, "texture": SubResource("frame0")}],
"name": &"idle", "loop": true, "speed": 8.0
}]
[node name="Player" type="AnimatedSprite2D"]
sprite_frames = SubResource("motion")
''')
        asset = next(item for item in self.call('dashboard.catalog', {})['result']['assets'] if item['path'] == 'textures/hero-sheet.png')
        self.assertEqual(asset['collection_type'], 'sprite')
        self.assertEqual(asset['resource_references'], ['player.tscn'])
        detail = self.call('dashboard.inspect', {'kind': asset['kind'], 'path': asset['path']})['result']
        self.assertNotIn('animations', detail)  # Classification does not invent decoded clips or frame geometry.

    def test_external_spriteframes_and_atlas_documents_use_only_scanned_resources(self):
        self.image('textures/hero.png')
        (self.root / 'frame.tres').write_text('[gd_resource type="AtlasTexture" format=3]\n[ext_resource type="Texture2D" path="res://textures/hero.png" id="sheet"]\n[resource]\natlas = ExtResource("sheet")\nregion = Rect2(0, 0, 96, 96)\n')
        (self.root / 'frames.tres').write_text('[gd_resource type="SpriteFrames" format=3]\n[ext_resource type="Texture2D" path="res://frame.tres" id="frame"]\n[resource]\nanimations = [{"frames": [{"texture": ExtResource("frame"), "duration": 1.0}], "name": &"idle"}]\n')
        (self.root / 'hero.tscn').write_text('[gd_scene format=3]\n[ext_resource type="SpriteFrames" path="res://frames.tres" id="motion"]\n[node name="Hero" type="AnimatedSprite2D"]\nsprite_frames = ExtResource("motion")\n')
        asset = next(item for item in self.call('dashboard.catalog', {})['result']['assets'] if item['path'] == 'textures/hero.png')
        self.assertEqual(asset['collection_type'], 'sprite')
        self.assertEqual(asset['resource_references'], ['frames.tres', 'hero.tscn'])

    def test_sprite_folders_are_fallbacks_and_tilesets_take_priority(self):
        self.image('assets/sprites/hero.png')
        self.image('assets/sprites/tilesets/ground.png')
        self.image('textures/interface.png')
        (self.root / 'ui.tscn').write_text('[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://textures/interface.png" id="art"]\n[node name="Image" type="TextureRect"]\ntexture = ExtResource("art")\n')
        images = {item['path']: item for item in self.call('dashboard.catalog', {})['result']['assets'] if item['origin'] == 'project'}
        self.assertEqual(images['assets/sprites/hero.png']['collection_type'], 'sprite')
        self.assertEqual(images['assets/sprites/hero.png']['sprite_evidence'], 'folder')
        self.assertEqual(images['assets/sprites/tilesets/ground.png']['collection_type'], 'tileset')
        self.assertEqual(images['textures/interface.png']['collection_type'], 'image')

    def native_fixture(self):
        from PIL import Image
        image = self.root / 'hero.png'
        sheet = Image.new('RGBA', (8, 4), 'red')
        sheet.paste('blue', (4, 0, 8, 4))
        sheet.save(image)
        resource = self.root / 'hero.tres'
        resource.write_text('''[gd_resource type="SpriteFrames" format=3]
[ext_resource type="Texture2D" path="res://hero.png" id="sheet"]
[sub_resource type="AtlasTexture" id="one"]
atlas = ExtResource("sheet")
region = Rect2(0, 0, 4, 4)
[sub_resource type="AtlasTexture" id="two"]
atlas = ExtResource("sheet")
region = Rect2(4, 0, 4, 4)
[resource]
animations = [{"name": &"Walk Left", "speed": 5.0, "loop": false,
"frames": [{"texture": SubResource("one"), "duration": 1.0}, {"texture": SubResource("two"), "duration": 2.0}]}]
''')
        return {'kind': 'image', 'path': 'hero.png', 'resources': ['hero.tres']}, resource

    def test_native_sprite_crops_pixels_and_preserves_timing_and_loop(self):
        import base64
        import io
        from PIL import Image
        data, resource = self.native_fixture()
        before = resource.read_bytes(), (self.root / 'hero.png').read_bytes()
        catalog = self.call('dashboard.catalog', {})['result']
        self.assertEqual(next(item for item in catalog['assets'] if item['path'] == 'hero.png')['sprite_resources'], ['hero.tres'])
        detail = self.call('dashboard.inspect', data)['result']
        self.assertEqual((detail['width'], detail['height']), (4, 4))
        self.assertEqual(detail['sheet_size'], [8, 4])
        clip = detail['animations'][0]
        self.assertEqual(clip['name'], 'Walk Left')
        self.assertFalse(clip['loop'])
        self.assertEqual(clip['duration_ms'], 600)
        for role in ['thumbnail', 'image', 'atlas', clip['media_key'], clip['contact_key']]:
            media = self.call('dashboard.media', dict(data, image=role, revision_hash=detail['revision_hash']))['result']
            with Image.open(io.BytesIO(base64.b64decode(media['data']))) as image:
                self.assertEqual(image.getpixel((0, 0)), (255, 0, 0, 255))
                if role == clip['media_key']:
                    self.assertEqual(image.n_frames, 2)
                    self.assertEqual(image.info['loop'], 1)
                    self.assertEqual(image.info['duration'], 200)
                    image.seek(1)
                    self.assertEqual(image.info['duration'], 400)
                    self.assertEqual(image.getpixel((0, 0)), (0, 0, 255, 255))
        self.assertEqual((resource.read_bytes(), (self.root / 'hero.png').read_bytes()), before)

    def test_native_metadata_changes_invalidate_previews_and_need_read_grants(self):
        data, resource = self.native_fixture()
        detail = self.call('dashboard.inspect', data)['result']
        planned = execute('dashboard.inspect', data, self.root, prepare_only=True)
        self.assertIn(str(resource), planned['access']['reads'])
        self.assertEqual(execute('dashboard.inspect', data, self.root, surface='native', authorized={'reads': [str(self.root / 'hero.png')], 'writes': []})['error']['code'], 'forbidden')
        resource.write_text(resource.read_text().replace('5.0', '10.0'))
        stale = execute('dashboard.media', dict(data, image='thumbnail', revision_hash=detail['revision_hash']), self.root)
        self.assertFalse(stale['ok'])
        self.assertIn('changed', stale['error']['message'].lower())

    def test_native_outside_regions_and_decoded_motion_budget_are_refused(self):
        data, resource = self.native_fixture()
        original = resource.read_text()
        resource.write_text(original.replace('Rect2(4, 0, 4, 4)', 'Rect2(7, 0, 4, 4)'))
        result = execute('dashboard.inspect', data, self.root)
        self.assertFalse(result['ok'])
        resource.write_text(original)
        with mock.patch('godot_sprite.MAX_DECODED_BYTES', 100):
            self.assertFalse(execute('dashboard.inspect', data, self.root)['ok'])

    def test_native_sprite2d_grid_uses_explicit_frame_not_whole_sheet(self):
        data, _ = self.native_fixture()
        scene = self.root / 'static.tscn'
        scene.write_text('[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://hero.png" id="art"]\n[node name="Hero" type="Sprite2D"]\ntexture = ExtResource("art")\nhframes = 2\nvframes = 1\nframe = 1\n')
        data['resources'] = ['static.tscn']
        detail = self.call('dashboard.inspect', data)['result']
        self.assertEqual((detail['width'], detail['height']), (4, 4))
        self.assertEqual(detail['animations'], [])

    def test_resource_cycles_and_outside_paths_do_not_expand_read_authority(self):
        self.image('textures/unrelated.png')
        (self.root / 'cycle.tres').write_text('[gd_resource type="AtlasTexture" format=3]\n[ext_resource type="Texture2D" path="res://cycle.tres" id="cycle"]\n[resource]\natlas = ExtResource("cycle")\n')
        (self.root / 'frames.tres').write_text('[gd_resource type="SpriteFrames" format=3]\n[ext_resource type="Texture2D" path="res://cycle.tres" id="frame"]\n[resource]\nanimations = [{"frames": [{"texture": ExtResource("frame")}]}]\n')
        (self.root / 'outside.tscn').write_text('[gd_scene format=3]\n[ext_resource type="Texture2D" path="res://../secret.png" id="bad"]\n[node name="Bad" type="Sprite2D"]\ntexture = ExtResource("bad")\n')
        result = self.call('dashboard.catalog', {})
        asset = next(item for item in result['result']['assets'] if item['path'] == 'textures/unrelated.png')
        self.assertEqual(asset['collection_type'], 'image')
        self.assertGreaterEqual(result['result']['unavailable'], 1)
        self.assertTrue(all(str(self.root) in path for path in result['access']['reads']))


class DashboardAdapterTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node required')
    def test_local_dashboard_transport(self):
        result = subprocess.run(['node', '--test', str(ROOT / 'tests/dashboard.test.mjs')], capture_output=True, text=True,
                                env={**os.environ, 'DAYDREAM_TEST_PYTHON': sys.executable}, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
