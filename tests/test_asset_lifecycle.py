import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from operations import execute
from asset_lifecycle import friendly_name
from review_fixture import create as create_fixture
import sprite_store as store

SOURCE = {'schema_version': 1, 'name': 'Potion Shop Floor', 'width': 4, 'height': 4,
          'palette': {'a': '#aabbcc', 'b': '#334455'}, 'pixels': ['aaaa'] * 4}


class FriendlyNameTests(unittest.TestCase):
    def test_friendly_labels_are_preserved_and_safe_ids_are_derived(self):
        for name in ('Potion Shop Floor', 'Floor: "Moonlight"', '42 Bottles!', 'Étage', '床', 'x' * 120, 'a/b\\c'):
            label, slug = friendly_name(name)
            self.assertEqual(label, name)
            self.assertRegex(slug, r'^[a-z][a-z0-9_-]{0,47}$')
        self.assertEqual(friendly_name('hut_floor'), ('hut_floor', 'hut_floor'))
        with self.assertRaises(ValueError): friendly_name(' ')


@unittest.skipUnless(importlib.util.find_spec('PIL'), 'optional Pillow required')
class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root/'project.godot').write_text('config_version=5\n')
        self.call('project.init', {'apply': True})

    def call(self, op, data, **kwargs):
        result = execute(op, data, self.root, **kwargs)
        self.assertTrue(result['ok'], result)
        return result

    def create(self):
        result = self.call('sprite.create', {'source': SOURCE, 'apply': True})['result']
        return str(Path(result['directory']).relative_to(self.root))

    def approve(self, bundle, kind='sprite'):
        revision = self.call('review.inspect', {'kind': kind, 'bundle': bundle})['result']['revision_hash']
        self.call(kind + '.approve', {'bundle': bundle, 'revision_hash': revision, 'reviewer': 'synthetic fixture', 'apply': True})

    def edit(self, bundle):
        result = self.call('sprite.edit', {'bundle': bundle, 'patch': {'schema_version': 1, 'operations': [{'op': 'recolor', 'symbol': 'a', 'color': '#112233'}]}, 'apply': True})
        return str(Path(result['result']['directory']).relative_to(self.root))

    def test_automatic_revisions_are_hidden_distinct_and_discoverable(self):
        preview = self.call('sprite.create', {'source': SOURCE})
        self.assertFalse((self.root/'.daydream/revisions').exists())
        first = self.create()
        second = self.edit(first)
        self.assertTrue(first.startswith('.daydream/revisions/sprite/potion-shop-floor/'))
        self.assertNotEqual(first, second)
        self.assertTrue((self.root/first/'source.json').exists())
        self.assertEqual(json.loads((self.root/second/'manifest.json').read_text())['provenance']['display_name'], 'Potion Shop Floor')
        self.assertFalse((self.root/'art').exists())
        listed = self.call('assets.list', {})['result']['assets']
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]['bundle'], second)
        self.assertEqual(listed[0]['older_revisions'], 1)
        history = self.call('assets.list', {'history': True})['result']['assets']
        self.assertEqual(len(history), 2)
        self.assertEqual(preview['result']['display_name'], 'Potion Shop Floor')

    def test_copy_automatically_resolves_collisions_with_regular_files_and_registry(self):
        bundle = self.create(); self.approve(bundle)
        directory = self.root/'assets/sprites'; directory.mkdir(parents=True)
        (directory/'potion-shop-floor.png.import').write_text('user sidecar')
        plan = self.call('sprite.import', {'bundle': bundle, 'strategy': 'copy'})
        self.assertEqual(plan['result']['asset_name'], 'potion-shop-floor-2')
        self.call('sprite.import', {'bundle': bundle, 'strategy': 'copy', 'plan_hash': plan['result']['plan_hash'], 'apply': True})
        next_plan = self.call('sprite.import', {'bundle': bundle, 'strategy': 'copy'})
        self.assertEqual(next_plan['result']['asset_name'], 'potion-shop-floor-3')
        self.assertEqual((directory/'potion-shop-floor.png.import').read_text(), 'user sidecar')

    def test_safe_update_keeps_paths_and_preserves_exact_old_bytes_and_sidecars(self):
        first = self.create(); self.approve(first)
        self.call('sprite.import', {'bundle': first, 'strategy': 'copy', 'apply': True})
        old_index = (self.root/'.daydream/assets.json').read_bytes()
        record = json.loads(old_index)['assets'][0]
        old_files = {p: (self.root/p).read_bytes() for p in record['paths'].values()}
        (self.root/(record['paths']['texture'] + '.import')).write_text('godot sidecar')
        second = self.edit(first); self.approve(second)
        data = {'bundle': second, 'strategy': 'update', 'target': record['name']}
        plan = self.call('sprite.import', data)['result']
        self.assertEqual(set(plan['replace']), set(old_files))
        self.assertEqual(plan['create'], [])
        self.assertFalse((self.root/plan['history']).exists())
        self.assertFalse(execute('sprite.import', {**data, 'apply': True}, self.root)['ok'])
        self.call('sprite.import', {**data, 'plan_hash': plan['plan_hash'], 'apply': True})
        current = json.loads((self.root/'.daydream/assets.json').read_bytes())['assets']
        self.assertEqual(len(current), 1)
        self.assertEqual(current[0]['paths'], record['paths'])
        for p, contents in old_files.items(): self.assertEqual((self.root/plan['history']/'files'/p).read_bytes(), contents)
        self.assertEqual((self.root/plan['history']/'assets-before.json').read_bytes(), old_index)
        self.assertTrue((self.root/plan['history']/'applied.json').exists())
        self.assertEqual((self.root/(record['paths']['texture'] + '.import')).read_text(), 'godot sidecar')

    def test_manual_edit_stale_plan_and_missing_backup_permission_block_updates(self):
        first = self.create(); self.approve(first)
        self.call('sprite.import', {'bundle': first, 'apply': True})
        second = self.edit(first); self.approve(second)
        data = {'bundle': second, 'strategy': 'update', 'target': 'potion-shop-floor'}
        prepared = execute('sprite.import', data, self.root, surface='native', prepare_only=True)
        resolved = execute('sprite.import', data, self.root, surface='native', resolve_only=True, authorized={'reads': prepared['access']['reads'], 'writes': []})
        self.assertTrue(resolved['ok'], resolved)
        preview = self.call('sprite.import', data, surface='native', authorized={'reads': resolved['access']['reads'], 'writes': []})
        grants = {'reads': preview['access']['reads'], 'writes': [str(self.root/p) for p in preview['result']['replace']]}
        denied = execute('sprite.import', {**data, 'apply': True, 'plan_hash': preview['result']['plan_hash']}, self.root, surface='native', authorized=grants)
        self.assertEqual(denied['error']['code'], 'forbidden')
        scene = self.root/'assets/sprites/potion-shop-floor.tscn'
        scene.write_text(scene.read_text() + '\n; manual edit\n')
        protected = execute('sprite.import', {**data, 'apply': True, 'plan_hash': preview['result']['plan_hash']}, self.root)
        self.assertEqual(protected['error']['code'], 'conflict')
        self.assertTrue(scene.read_text().endswith('; manual edit\n'))
        choices = self.call('assets.options', {'bundle': second, 'kind': 'sprite'})['result']
        self.assertFalse(choices['targets'][0]['can_update'])
        self.assertEqual(self.call('assets.list', {})['result']['active'][0]['state'], 'modified')

    def test_interruption_retains_backups_and_detects_partial_updates_on_retry(self):
        first = self.create(); self.approve(first)
        self.call('sprite.import', {'bundle': first, 'apply': True})
        old = (self.root/'assets/sprites/potion-shop-floor.png').read_bytes()
        second = self.edit(first); self.approve(second)
        data = {'bundle': second, 'strategy': 'update', 'target': 'potion-shop-floor'}
        plan = self.call('sprite.import', data)['result']
        real_replace = store.os.replace
        def replacing(src, dst, **kwargs):
            if dst.endswith('.tscn'): raise OSError('simulated interruption')
            return real_replace(src, dst, **kwargs)
        with mock.patch.object(store.os, 'replace', side_effect=replacing):
            result = execute('sprite.import', {**data, 'plan_hash': plan['plan_hash'], 'apply': True}, self.root)
        self.assertFalse(result['ok'])
        self.assertEqual((self.root/plan['history']/'files/assets/sprites/potion-shop-floor.png').read_bytes(), old)
        self.assertFalse((self.root/plan['history']/'applied.json').exists())
        self.assertFalse(execute('sprite.import', {**data, 'plan_hash': plan['plan_hash'], 'apply': True}, self.root)['ok'])

    def test_detected_editor_write_during_update_is_preserved(self):
        first = self.create(); self.approve(first)
        self.call('sprite.import', {'bundle': first, 'apply': True})
        second = self.edit(first); self.approve(second)
        data = {'bundle': second, 'strategy': 'update', 'target': 'potion-shop-floor'}
        plan = self.call('sprite.import', data)['result']
        scene = self.root/'assets/sprites/potion-shop-floor.tscn'
        user_edit = scene.read_bytes() + b'\n; concurrent editor save\n'
        real_write = store.write_new
        def writing(directory, name, contents, **kwargs):
            real_write(directory, name, contents, **kwargs)
            if name.startswith('.daydream-update-'):
                scene.write_bytes(user_edit)
        with mock.patch.object(store, 'write_new', side_effect=writing):
            result = execute('sprite.import', {**data, 'plan_hash': plan['plan_hash'], 'apply': True}, self.root)
        self.assertFalse(result['ok'])
        self.assertEqual(scene.read_bytes(), user_edit)
        self.assertFalse((self.root/plan['history']/'applied.json').exists())

    def test_discovery_requires_metadata_then_exact_output_grants(self):
        bundle = self.create(); self.approve(bundle)
        self.call('sprite.import', {'bundle': bundle, 'apply': True})
        prepared = execute('assets.list', {}, self.root, surface='native', prepare_only=True)
        grants = {'reads': prepared['access']['reads'], 'writes': []}
        self.assertFalse(execute('assets.list', {}, self.root, surface='native', authorized=grants)['ok'])
        resolved = execute('assets.list', {}, self.root, surface='native', resolve_only=True, authorized=grants)
        self.assertTrue(resolved['ok'], resolved)
        self.call('assets.list', {}, surface='native', authorized={'reads': resolved['access']['reads'], 'writes': []})

    def test_animation_and_tileset_updates_use_same_history_contract(self):
        bundles = create_fixture(self.root)
        for kind, bundle in bundles.items():
            self.approve(bundle, kind)
            first = self.call(kind + '.import', {'bundle': bundle, 'apply': True})['result']
            if kind == 'sprite':
                change = {'patch': {'schema_version': 1, 'operations': [{'op': 'recolor', 'symbol': 'a', 'color': '#123456'}]}}
            elif kind == 'animation':
                change = {'patch': {'schema_version': 1, 'operations': [{'op': 'recolor', 'symbol': 'a', 'color': '#123456'}]}}
            else:
                change = {'tiles': [{'id': 'floor', 'collision_preset': {'preset': 'platform'}}]}
            second = self.call(kind + '.edit', {'bundle': bundle, **change, 'apply': True})['result']['directory']
            self.approve(second, kind)
            data = {'bundle': second, 'strategy': 'update', 'target': first['asset_name']}
            plan = self.call(kind + '.import', data)['result']
            self.call(kind + '.import', {**data, 'plan_hash': plan['plan_hash'], 'apply': True})
            self.assertEqual(plan['scene'], first['scene'])
            self.assertTrue((self.root/plan['history']/'applied.json').exists())

    def test_update_refuses_tile_identity_changes_and_preserves_legacy_bundles(self):
        bundles = create_fixture(self.root)
        self.approve(bundles['tileset'], 'tileset')
        self.call('tileset.import', {'bundle': bundles['tileset'], 'apply': True})
        original = json.loads((self.root/bundles['tileset']/'source.json').read_bytes())
        original['tiles'][0]['id'] = 'different'
        original['cells'][0]['tile'] = 'different'
        new = self.call('tileset.create', {'source': original, 'apply': True})['result']['directory']
        self.approve(new, 'tileset')
        denied = execute('tileset.import', {'bundle': new, 'strategy': 'update', 'target': 'floor'}, self.root)
        self.assertEqual(denied['error']['code'], 'conflict')
        self.assertIn('Tile IDs', denied['error']['message'])
        self.assertTrue((self.root/bundles['tileset']/'source.json').exists())
