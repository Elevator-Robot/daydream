"""Read-only project collection and asset inspector shared by dashboard/CLI/tools."""

import base64
from datetime import datetime, timezone
import io
import os
from pathlib import Path
import re
import stat

import asset_access
from asset_lifecycle import discover_reads as discover_candidates, list_assets, metadata, record_paths
from sprite_core import digest, pillow, png_bytes, read_regular

IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga', '.svg'}
SKIP = {'.git', '.godot', '.daydream', '.opencode', 'node_modules', '__pycache__', 'build', 'dist', 'vendor'}
MAX_FILES = 1000
MAX_RESOURCES = 500


def identity(kind, path):
    return digest((kind + '\0' + path).encode())[:24]


def discover_reads(context, operation, data):
    if operation in {'dashboard.inspect', 'dashboard.media'}:
        context.native_sprite_model = None
        if data.get('kind') == 'image' and data.get('resources'):
            context.dashboard_resources = [context.path(path) for path in data['resources']]
            project_image_references(context)
            from godot_sprite import sprite_model
            context.native_sprite_model = sprite_model(context.godot_documents, context.relative(context.path(data['path'])))
            context.native_resource_hashes = context.godot_resource_hashes
        return set()
    reads = discover_candidates(context, 'assets.list', {})
    files, resources, pending, visited = [], [], [context.root], 0
    managed = set(context.asset_bundles)
    while pending and visited < 3000 and len(files) < MAX_FILES:
        directory = pending.pop(0)
        visited += 1
        if directory in managed:
            continue
        try:
            context.path(str(directory))
            with os.scandir(directory) as entries:
                for index, entry in enumerate(entries):
                    if index >= 4000:
                        context.asset_truncated = True
                        break
                    if entry.name.startswith('.') or entry.name in SKIP or entry.is_symlink():
                        continue
                    path = Path(entry.path)
                    if entry.is_dir(follow_symlinks=False):
                        if len(pending) < 3000:
                            pending.append(path)
                        else:
                            context.asset_truncated = True
                    elif entry.is_file(follow_symlinks=False) and path.suffix.lower() in IMAGE_EXTENSIONS:
                        files.append(context.path(str(path)))
                        if len(files) >= MAX_FILES:
                            context.asset_truncated = True
                            break
                    elif entry.is_file(follow_symlinks=False) and path.suffix.lower() in {'.tres', '.tscn'}:
                        if len(resources) < MAX_RESOURCES:
                            resources.append(context.path(str(path)))
                        else:
                            context.asset_truncated = True
        except FileNotFoundError:
            continue
    context.dashboard_files = files
    context.dashboard_resources = resources
    context.asset_truncated = context.asset_truncated or bool(pending)
    return reads | {str(file) for file in files + resources}


def project_image_references(context):
    """Classify existing artwork from bounded, already-authorized Godot text.

    Follow only known texture/SpriteFrames relationships in the scanned documents.
    Never load extra files, execute scripts or reconstruct gameplay/clip data.
    """
    atlases, sprites, documents, resource_hashes, graph_limited, unavailable = {}, {}, {}, {}, set(), 0
    header = re.compile(r'^\[(ext_resource|sub_resource|node|resource|gd_resource|gd_scene)(?:[ \t]+([^\n]*))?\][ \t]*$', re.MULTILINE)
    expression = re.compile(r'(ExtResource|SubResource)\("([^"\n]+)"\)')
    for file in context.dashboard_resources:
        try:
            raw = read_regular(file, 4 * 1024 * 1024)
            text = raw.decode('utf-8')
            matches = list(header.finditer(text))
            blocks = []
            for index, match in enumerate(matches):
                attrs = dict(re.findall(r'(\w+)="([^"\n]*)"', match.group(2) or ''))
                body = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
                if attrs.get('path', '').startswith('res://'):
                    attrs['relative_path'] = context.relative(context.path(attrs['path'][6:]))
                blocks.append((match.group(1), attrs, body))
            documents[context.relative(file)] = blocks
            resource_hashes[context.relative(file)] = digest(raw)
        except (OSError, ValueError, UnicodeError):
            unavailable += 1

    def property_ref(body, name):
        value = re.search(r'^' + name + r'\s*=\s*((?:ExtResource|SubResource)\("[^"\n]+"\))', body, re.MULTILINE)
        return value.group(1) if value else ''

    def resolve(file, value, seen=None):
        seen = set() if seen is None else seen
        key = (file, value)
        if key in seen:
            return set()
        if len(seen) >= 128:
            graph_limited.add(file)
            return set()
        seen.add(key)
        blocks = documents.get(file, [])
        if value == 'root':
            root_type = next((attrs.get('type') for kind, attrs, _ in blocks if kind == 'gd_resource'), None)
            block = next(((root_type, body) for kind, _, body in blocks if kind == 'resource'), None)
        else:
            match = expression.fullmatch(value)
            if not match:
                return set()
            target_kind = 'ext_resource' if match.group(1) == 'ExtResource' else 'sub_resource'
            target = next(((attrs, body) for kind, attrs, body in blocks if kind == target_kind and attrs.get('id') == match.group(2)), None)
            if not target:
                return set()
            attrs, body = target
            if target_kind == 'ext_resource':
                path = attrs.get('relative_path', '')
                if attrs.get('type') not in {'Texture2D', 'AtlasTexture', 'SpriteFrames'}:
                    return set()
                if Path(path).suffix.lower() in IMAGE_EXTENSIONS and attrs.get('type') != 'SpriteFrames':
                    return {path}
                return resolve(path, 'root', seen)
            block = (attrs.get('type'), body)
        if not block:
            return set()
        resource_type, body = block
        if resource_type == 'AtlasTexture':
            return resolve(file, property_ref(body, 'atlas'), seen)
        if resource_type == 'SpriteFrames':
            result = set()
            for match in re.finditer(r'"texture"\s*:\s*((?:ExtResource|SubResource)\("[^"\n]+"\))', body):
                result |= resolve(file, match.group(1), seen)
            return result
        return set()

    for file, blocks in documents.items():
        root_type = next((attrs.get('type') for kind, attrs, _ in blocks if kind == 'gd_resource'), None)
        for kind, attrs, body in blocks:
            resource_type = root_type if kind == 'resource' else attrs.get('type')
            if resource_type == 'TileSetAtlasSource':
                for image in resolve(file, property_ref(body, 'texture')):
                    atlases.setdefault(image, set()).add(file)
            elif resource_type == 'SpriteFrames':
                value = 'root' if kind == 'resource' else f'SubResource("{attrs.get("id", "")}")'
                for image in resolve(file, value):
                    sprites.setdefault(image, set()).add(file)
            elif kind == 'node' and resource_type in {'Sprite2D', 'AnimatedSprite2D'}:
                prop = 'texture' if resource_type == 'Sprite2D' else 'sprite_frames'
                for image in resolve(file, property_ref(body, prop)):
                    sprites.setdefault(image, set()).add(file)
    context.godot_documents = documents
    context.godot_resource_hashes = resource_hashes
    return atlases, sprites, unavailable + len(graph_limited)


def sprite_links(entries):
    """Associate by recorded source hashes, following animation edit ancestry."""
    by_hash = {entry.get('revision_hash'): entry for entry in entries if entry.get('revision_hash')}
    for entry in entries:
        entry['sprite_groups'] = []
        if entry['kind'] != 'animation':
            continue
        seen, pending = set(), [entry]
        while pending and len(seen) < 500:
            parent = pending.pop()
            hash_value = parent.get('revision_hash')
            if hash_value in seen:
                continue
            seen.add(hash_value)
            parents = parent.get('parent_revision_hashes')
            hashes = [parent.get('base_revision_hash'), parent.get('parent_revision_hash'), *(parents[:32] if isinstance(parents, list) else [])]
            for value in hashes:
                if not isinstance(value, str):
                    continue
                source = by_hash.get(value)
                if not source:
                    continue
                if source['kind'] == 'sprite' and source['group'] not in entry['sprite_groups']:
                    entry['sprite_groups'].append(source['group'])
                elif source['kind'] == 'animation':
                    pending.append(source)


def catalog(context, data):
    result = list_assets(context, {'history': True})
    _, index = metadata(context)
    records = []
    for record in index['assets']:
        if record.get('kind') not in {'sprite', 'sprite_animation', 'tileset'}:
            continue
        paths = record_paths(context, record)
        active = next((item for item in result['active'] if item['id'] == record['name']), {})
        records.append({**active, 'paths': paths})
    entries = []
    by_hash = {row['revision_hash']: row for row in result['assets']}
    for row in result['assets']:
        kind = 'animation' if row['kind'] == 'sprite_animation' else row['kind']
        family = identity(kind, row['id'])
        imports = [record for record in records if
                   (by_hash.get(record.get('revision_hash'), {}).get('id'), record['kind']) == (row['id'], row['kind'])]
        entries.append({**row, 'id': identity(kind, row['bundle']), 'asset_id': row['id'],
                        'group': family, 'kind': kind, 'origin': 'daydream', 'path': row['bundle'], 'imports': imports})
    # Registered textures already have a managed card; don't count their PNG twice.
    registered = {record['paths'].get('texture') for record in records}
    references, sprite_references, unreadable_resources = project_image_references(context)
    unavailable = result['invalid_candidates'] + unreadable_resources
    for file in context.dashboard_files:
        relative = context.relative(file)
        if relative in registered:
            continue
        asset_access.read(file)
        try:
            info = file.lstat()
            if not stat.S_ISREG(info.st_mode):
                raise ValueError('Not a regular image')
            key = identity('image', relative)
            atlas_folder = any(part.lower() in {'tilesets', 'tileset', 'tilemaps'} for part in file.relative_to(context.root).parts[:-1])
            sprite_folder = any(part.lower() in {'sprites', 'sprite'} for part in file.relative_to(context.root).parts[:-1])
            is_atlas = relative in references or atlas_folder
            is_sprite = not is_atlas and (relative in sprite_references or sprite_folder)
            sprite_resources = []
            if is_sprite:
                from godot_sprite import sprite_model
                sprite_resources = sprite_model(context.godot_documents, relative)['resources']
            entries.append({'id': key, 'group': key, 'name': file.stem, 'kind': 'image',
                            'origin': 'project', 'path': relative, 'state': 'project_file', 'is_latest': True,
                            'modified_at': info.st_mtime_ns, 'bytes': info.st_size,
                            'format': file.suffix[1:].upper(), 'imports': [],
                            'collection_type': 'tileset' if is_atlas else 'sprite' if is_sprite else 'image',
                            'tileset_evidence': 'godot_reference' if relative in references else 'folder' if atlas_folder else None,
                            'sprite_evidence': 'godot_reference' if is_sprite and relative in sprite_references else 'folder' if is_sprite else None,
                            'sprite_resources': sprite_resources,
                            'resource_references': sorted((references if is_atlas else sprite_references).get(relative, []))})
        except (OSError, ValueError):
            unavailable += 1
    # Imported outputs whose staged revision is absent remain visible in the library.
    for record in records:
        if record.get('revision_hash') in by_hash or not record['paths'].get('texture'):
            continue
        relative = record['paths']['texture']
        key = identity('image', relative)
        entries.append({'id': key, 'group': key, 'name': record['name'], 'kind': 'image',
                        'origin': 'project', 'path': relative, 'state': record['state'], 'is_latest': True,
                        'imports': [record], 'modified_at': 0, 'format': Path(relative).suffix[1:].upper(),
                        'collection_type': 'tileset' if record['kind'] == 'tileset' else 'sprite',
                        'sprite_evidence': 'registry' if record['kind'] != 'tileset' else None})
    entries.sort(key=lambda item: (-item['modified_at'], item['name'], item['id']))
    sprite_links(entries)
    project = read_regular(context.path('project.godot'), 1024 * 1024).decode('utf-8', errors='replace')
    name = re.search(r'^config/name="([^"\n]+)"', project, re.MULTILINE)
    return {'project': {'name': name.group(1) if name else context.root.name, 'directory': str(context.root)},
            'generated_at': datetime.now(timezone.utc).isoformat(), 'assets': entries,
            'imports': records, 'truncated': result['truncated'], 'unavailable': unavailable,
            'scope': 'Daydream revisions and supported project images. Godot sprite/atlas references and sprite/tileset folders determine collection categories. Existing images remain project files; frame geometry and animation playback are not inferred. Hidden/build folders are excluded.',
            'limits': {'project_images': MAX_FILES, 'candidate_bundles': 500}}, []


def project_image(context, data):
    path = context.path(data['path'])
    if path.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError('Choose a supported project image')
    raw = read_regular(path, 32 * 1024 * 1024)
    if path.suffix.lower() == '.svg':
        raise ValueError('SVG is listed in the collection; raster preview is not supported. Inspect it in your image editor.')
    Image, _ = pillow()
    with Image.open(io.BytesIO(raw)) as image:
        if image.width * image.height > 16 * 1024 * 1024:
            raise ValueError('Image exceeds the 16-megapixel inspection limit')
        result = {'name': path.stem, 'kind': 'image', 'width': image.width, 'height': image.height,
                  'format': image.format, 'bytes': len(raw), 'revision_hash': digest(raw),
                  'animated': bool(getattr(image, 'is_animated', False))}
        converted = image.convert('RGBA')
        colors = converted.getcolors(128)
        result['palette'] = ['#' + ''.join(f'{channel:02x}' for channel in rgba) for _, rgba in sorted(colors or [], reverse=True) if rgba[3]]
        return result, converted


def revision(context, data):
    from operation_handlers import review_loader
    return review_loader(data['kind'])(context.path(data['path']))


def verify_hash(actual, data):
    if data.get('revision_hash') and data['revision_hash'] != actual:
        raise ValueError('This asset changed since the dashboard loaded. Refresh the collection before inspecting it.')


def inspect_asset(context, data):
    if data['kind'] == 'image':
        model = getattr(context, 'native_sprite_model', None)
        if model and model['first']:
            from godot_sprite import decode
            fingerprint, frames, sheet_size = decode(context, data, model, context.native_resource_hashes)
            verify_hash(fingerprint, data)
            first = frames[model['first']]
            colors = first.getcolors(128)
            return {'name': context.path(data['path']).stem, 'kind': 'image', 'path': data['path'],
                    'width': first.width, 'height': first.height, 'sheet_size': sheet_size, 'format': 'PNG',
                    'native_sprite': True, 'revision_hash': fingerprint, 'state': 'project_file',
                    'palette': ['#' + ''.join(f'{channel:02x}' for channel in rgba) for _, rgba in sorted(colors or [], reverse=True) if rgba[3]],
                    'frames': [{'id': key, 'index': index} for index, key in enumerate(frames)],
                    'atlas_columns': min(8, len(frames)), 'animations': model['animations'],
                    'default_animation': model['animations'][0]['name'] if model['animations'] else None,
                    'resource_warnings': model['warnings'],
                    'note': 'Existing Godot sprite. Previews use its recorded frame regions and clip timing; the source sheet and resources are unchanged.'}, []
        info, image = project_image(context, data)
        image.close()
        verify_hash(info['revision_hash'], data)
        return {**info, 'path': data['path'], 'state': 'project_file',
                'note': 'Existing project artwork. This is not a Daydream approval or revision. Animated project files show their first frame.' if info['animated'] else 'Existing project artwork; not a Daydream approval or revision.'}, []
    from review_core import status
    import animation_core
    import tileset_core
    import collision_core
    loaded = revision(context, data)
    verify_hash(loaded['revision_hash'], data)
    source = loaded['source']
    result = {'name': loaded['manifest'].get('provenance', {}).get('display_name', source['name']),
              'path': data['path'], **status(loaded), 'kind': data['kind'],
              'provenance': loaded['manifest'].get('provenance', {}),
              'files': [{'name': name, 'sha256': value} for name, value in loaded['manifest']['files'].items()]}
    if data['kind'] in {'sprite', 'animation'}:
        palette = source['palette'] if data['kind'] == 'sprite' else source['frames'][0]['source']['palette']
        result.update(width=source['width'], height=source['height'], palette=list(palette.values()))
    if data['kind'] == 'animation':
        result.update(pivot=source['pivot'], default_animation=source['default_animation'],
                      frames=[{'id': frame['id'], 'index': index} for index, frame in enumerate(source['frames'])],
                      animations=[{**clip, 'duration_ms': sum(animation_core.motion_frames(source, clip)[1])} for clip in source['animations']])
        result['atlas_columns'] = min(8, len(source['frames']))
    elif data['kind'] == 'tileset':
        first = source['tiles'][0]['source']
        colors = sorted({color for tile in source['tiles'] for color in tile['source']['palette'].values()})
        result.update(width=first['width'], height=first['height'], palette=colors[:128], palette_count=len(colors),
                      atlas_columns=min(8, len(source['tiles'])), terrains=source['terrains'],
                      tiles=[{key: value for key, value in tile.items() if key != 'source'} for tile in source['tiles']],
                      cells=source['cells'], seams=tileset_core.seams(source), collisions=collision_core.summary(source),
                      collision_layer=source['collision_layer'], collision_mask=source['collision_mask'],
                      has_collision_preview='collisions.png' in loaded['files'])
    return result, []


def media(context, data):
    role = data.get('image', 'thumbnail')
    Image, _ = pillow()
    if data['kind'] == 'image':
        model = getattr(context, 'native_sprite_model', None)
        if model and model['first']:
            from godot_sprite import decode, media_bytes
            fingerprint, frames, _ = decode(context, data, model, context.native_resource_hashes)
            verify_hash(fingerprint, data)
            raw, (width, height) = media_bytes(model, frames, role)
            if len(raw) > 8 * 1024 * 1024: raise ValueError('Native sprite preview exceeds the 8 MiB limit')
            return {'revision_hash': fingerprint, 'width': width, 'height': height, 'mime': 'image/png', 'data': base64.b64encode(raw).decode()}, []
        if role not in {'thumbnail', 'image'}:
            raise ValueError('Unknown project-image view')
        info, image = project_image(context, data)
        verify_hash(info['revision_hash'], data)
        if role == 'thumbnail':
            image.thumbnail((256, 192), Image.Resampling.NEAREST)
        raw = png_bytes(image)
        width, height = image.size
        image.close()
    else:
        loaded = revision(context, data)
        verify_hash(loaded['revision_hash'], data)
        source = loaded['source']
        files = {'sprite': 'sprite.png'} if data['kind'] == 'sprite' else {'atlas': 'spritesheet.png'} if data['kind'] == 'animation' else {'atlas': 'atlas.png', 'layout': 'layout.png', 'collisions': 'collisions.png'}
        if data['kind'] == 'animation':
            for clip in source['animations']:
                files['motion:' + clip['name']] = clip['name'] + '.motion.png'
                files['contact:' + clip['name']] = clip['name'] + '.contact.png'
        filename = ('sprite.png' if data['kind'] == 'sprite' else 'spritesheet.png' if data['kind'] == 'animation' else 'layout.png') if role == 'thumbnail' else files.get(role)
        if not filename or filename not in loaded['manifest']['files']:
            raise ValueError('This view is not available for the selected revision')
        raw = read_regular(loaded['path'] / filename, 8 * 1024 * 1024)
        if digest(raw) != loaded['manifest']['files'][filename]:
            raise ValueError('Image changed while preparing the dashboard; refresh to inspect it again')
        with Image.open(io.BytesIO(raw)) as image:
            width, height = image.size
            if role == 'thumbnail':
                image = image.convert('RGBA')
                if data['kind'] == 'animation':
                    image = image.crop((0, 0, source['width'], source['height']))
                image.thumbnail((256, 192), Image.Resampling.NEAREST)
                raw = png_bytes(image)
                width, height = image.size
        info = {'revision_hash': loaded['revision_hash']}
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Dashboard image exceeds the 8 MiB limit')
    return {**info, 'width': width, 'height': height, 'mime': 'image/png', 'data': base64.b64encode(raw).decode()}, []
