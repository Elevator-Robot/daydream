"""Friendly identity, managed revision placement, discovery and guarded updates."""

import copy
import json
import os
from pathlib import Path
import re
import unicodedata

import asset_access
from asset_errors import AssetConflict
from sprite_core import NAME, digest, encoded, read_regular
from init_project import validate_document

KINDS = {"sprite": "sprite", "sprite_animation": "animation", "tileset": "tileset"}


def friendly_name(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 120 or any(ord(ch) < 32 for ch in value):
        raise ValueError("Give the asset a name of 1–120 characters, such as 'Potion Shop Floor'")
    label = value.strip()
    if NAME.fullmatch(label):
        return label, label
    ascii_name = unicodedata.normalize('NFKD', label).encode('ascii', 'ignore').decode().lower()
    slug = re.sub('[^a-z0-9]+', '-', ascii_name).strip('-')
    if not slug or not slug[0].isalpha():
        slug = 'asset-' + (slug or digest(label.encode())[:8])
    return label, slug[:48].rstrip('-')


def normalize_request(operation, data):
    """Normalize asset labels only; paths, frame/tile IDs and patches stay exact."""
    value = copy.deepcopy(data)
    label = None
    field = 'source' if operation in {'sprite.create', 'tileset.create'} else 'recipe' if operation == 'animation.create' else None
    if field and isinstance(value.get(field), dict) and 'name' in value[field]:
        label, value[field]['name'] = friendly_name(value[field]['name'])
    elif operation in {'sprite.from_png', 'animation.assemble', 'tileset.transitions'} and 'name' in value:
        label, value['name'] = friendly_name(value['name'])
    return value, label


def managed_output(context, kind, name, revision_hash):
    base = context.path(f'.daydream/revisions/{kind}/{name}')
    for number in range(1, 10001):
        output = context.path(str(base / f'{revision_hash}-{number:04d}'))
        if not os.path.lexists(output):
            return output
    raise ValueError("This asset has too many saved revisions; inspect its history before creating another")


def metadata(context):
    documents = {}
    for name in ('config.json', 'assets.json'):
        try:
            raw = read_regular(context.path('.daydream/' + name), 1024 * 1024)
            validate_document(context.root, name, raw.decode())
            documents[name] = json.loads(raw)
        except FileNotFoundError:
            documents[name] = {'paths': {'assets': 'assets', 'sources': 'art'}} if name == 'config.json' else {'assets': []}
    return documents['config.json'], documents['assets.json']


def record_paths(context, record):
    """Index metadata is untrusted. Restrict it to ordinary generated resource paths."""
    paths, hashes = record.get('paths'), record.get('sha256')
    if not isinstance(paths, dict) or not {'texture', 'scene', 'source'}.issubset(paths) or not isinstance(hashes, dict) or len(paths) > 8 or not isinstance(record.get('name'), str) or not NAME.fullmatch(record['name']):
        raise ValueError("This asset's registry record is incomplete; use a separate copy")
    if any(not isinstance(relative, str) for relative in paths.values()) or len(set(paths.values())) != len(paths) or set(paths.values()) != set(hashes):
        raise ValueError("This asset's registry paths/hashes do not agree; use a separate copy")
    for relative in paths.values():
        if not isinstance(relative, str) or Path(relative).is_absolute() or any(part.startswith('.') for part in Path(relative).parts) or Path(relative).suffix not in {'.png', '.json', '.tscn', '.tres', '.gd'}:
            raise ValueError("The asset registry contains an unsupported output path")
        context.path(relative)
        if not isinstance(hashes[relative], str) or not re.fullmatch('[0-9a-f]{64}', hashes[relative]):
            raise ValueError("The asset registry contains an invalid output hash")
    return paths


def find_record(index, name):
    records = [record for record in index['assets'] if record.get('name') == name and record.get('kind') in KINDS]
    if len(records) > 1:
        raise ValueError("Several registered assets have this ID; use a separate copy until the registry is reconciled")
    return records[0] if records else None


def discover_reads(context, operation, data):
    """Run after metadata-read permission, enumerate additional exact read paths."""
    config, index = metadata(context)
    reads = set()
    if operation == 'assets.list':
        starts = [context.path(config['paths']['sources']), context.path('.daydream/revisions')]
        pending, count = list(starts), 0
        bundles = []
        while pending and count < 2000 and len(bundles) < 500:
            directory = pending.pop(0); count += 1
            try:
                context.path(str(directory))
                with os.scandir(directory) as entries:
                    children = []
                    manifest = False
                    for i, entry in enumerate(entries):
                        if i >= 2000:
                            break
                        if entry.name == 'manifest.json' and entry.is_file(follow_symlinks=False): manifest = True
                        if entry.is_dir(follow_symlinks=False) and not entry.name.startswith('.'): children.append(Path(entry.path))
                if manifest:
                    bundles.append(directory)
                    from review_core import feedback_filenames
                    for name in ('manifest.json', 'approval.json', *feedback_filenames(directory)):
                        reads.add(str(context.path(str(directory / name))))
                else:
                    pending.extend(children[:max(0, 2000-len(pending))])
            except FileNotFoundError:
                continue
        context.asset_bundles = bundles
        context.asset_truncated = bool(pending)
    if operation.startswith('assets.') or data.get('strategy') == 'update':
        for record in index['assets']:
            if record.get('kind') not in KINDS:
                continue
            if data.get('strategy') == 'update' and record.get('name') != data.get('target'):
                continue
            for relative in record_paths(context, record).values():
                reads.add(str(context.path(relative)))
    return reads


def modified_files(context, record):
    paths = record_paths(context, record)
    changed = []
    for relative in paths.values():
        try:
            if digest(read_regular(context.path(relative), 32 * 1024 * 1024)) != record['sha256'][relative]: changed.append(relative)
        except FileNotFoundError:
            changed.append(relative)
    return changed


def list_assets(context, data):
    _, index = metadata(context)
    active = []
    for record in index['assets']:
        if record.get('kind') not in KINDS: continue
        changes = modified_files(context, record)
        label, _ = friendly_name(record.get('display_name', record['name']))
        active.append({'id': record['name'], 'name': label, 'kind': record['kind'],
                       'state': 'modified' if changes else 'imported', 'modified_files': changes,
                       'revision_hash': record.get('revision_hash'), 'scene': record['paths'].get('scene'),
                       'bundle': record.get('bundle'), 'layout': 'runtime' if 'layout' in record['paths'] else 'editor'})
    candidates, invalid = [], 0
    for bundle in context.asset_bundles:
        try:
            raw = read_regular(bundle / 'manifest.json', 1024 * 1024)
            manifest = json.loads(raw)
            if manifest.get('kind') not in KINDS or not isinstance(manifest.get('name'), str) or not NAME.fullmatch(manifest['name']): continue
            label, _ = friendly_name(manifest.get('provenance', {}).get('display_name', manifest['name']))
            hash_value = digest(raw)
            state = 'draft'
            for filename, decision in (('approval.json', 'approved'),):
                try:
                    record = json.loads(read_regular(bundle / filename, 65536))
                    if record.get('revision_hash') == hash_value: state = decision
                except FileNotFoundError: pass
            from review_core import load_feedback
            if load_feedback({'path': bundle, 'manifest': manifest, 'revision_hash': hash_value}):
                state = 'changes_requested'
            current = next((row for row in active if row['revision_hash'] == hash_value), None)
            if current and state != 'changes_requested': state = current['state']
            candidates.append({'bundle': context.relative(bundle), 'id': manifest['name'],
                               'name': label,
                               'kind': manifest['kind'], 'state': state, 'revision_hash': hash_value,
                               'parent_revision_hash': manifest.get('provenance', {}).get('parent_revision_hash'),
                               'modified_at': (bundle / 'manifest.json').stat().st_mtime_ns})
        except (ValueError, OSError, AttributeError): invalid += 1
    candidates.sort(key=lambda row: (-row['modified_at'], row['bundle']))
    groups = {}
    for row in candidates: groups.setdefault((row['kind'], row['id']), []).append(row)
    rows = candidates if data.get('history', False) else [dict(rows[0], older_revisions=len(rows)-1) for rows in groups.values()]
    return {'assets': rows, 'active': active, 'truncated': context.asset_truncated, 'invalid_candidates': invalid,
            'status_note': 'Discovery status only; opening review revalidates the exact artwork and metadata.'}


def options(context, data):
    from operation_handlers import review_loader
    revision = review_loader(data['kind'])(context.path(data['bundle']))
    _, index = metadata(context)
    kind = revision['manifest']['kind']
    targets = []
    for record in index['assets']:
        if record.get('kind') != kind: continue
        changed = modified_files(context, record)
        targets.append({'id': record['name'], 'name': record.get('display_name', record['name']),
                        'state': 'modified' if changed else 'imported', 'can_update': not changed,
                        'modified_files': changed, 'scene': record['paths'].get('scene'),
                        'layout': 'runtime' if 'layout' in record['paths'] else 'editor',
                        'same_revision': record.get('revision_hash') == revision['revision_hash']})
    return {'initialized': all(context.path('.daydream/' + name).is_file() for name in ('config.json', 'assets.json')),
            'name': revision['manifest'].get('provenance', {}).get('display_name', revision['source']['name']),
            'id': revision['source']['name'], 'targets': targets,
            'suggested_target': next((row['id'] for row in targets if row['id'] == revision['source']['name']), None)}


def unique_import_name(project, index, label, asset_dir, source_dir):
    _, slug = friendly_name(label)
    used = {record.get('name') for record in index['assets']}
    for number in range(1, 10001):
        suffix = '' if number == 1 else f'-{number}'
        candidate = slug[:48-len(suffix)] + suffix
        if candidate in used: continue
        # Any existing companion/sidecar blocks that stem; do not adopt files.
        if any(any((project / directory).glob(candidate + '.*')) for directory in (asset_dir, source_dir)): continue
        return candidate
    raise ValueError("Could not choose a free asset filename; choose a different display name")


def check_tile_identity(previous, revision):
    if revision['manifest']['kind'] != 'tileset': return
    from tileset_core import validate_source
    old = validate_source(json.loads(previous))
    new = revision['source']
    if (old.get('terrains') != new['terrains'] or len(old.get('tiles', [])) > len(new['tiles'])
            or min(8, len(old.get('tiles', []))) != min(8, len(new['tiles']))):
        raise AssetConflict("Terrain/atlas identity changed. Add a separate copy to protect maps using this TileSet")
    for a, b in zip(old['tiles'], new['tiles']):
        if a.get('id') != b['id'] or (a['source']['width'], a['source']['height']) != (b['source']['width'], b['source']['height']):
            raise AssetConflict("Tile IDs/order/size changed. Add a separate copy to protect existing maps")
