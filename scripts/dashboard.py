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


def atlas_references(context):
    """Read text only; identify direct TileSetAtlasSource texture references.

    No Godot execution, arbitrary resource recursion, or inferred tile geometry.
    Unsupported/binary/oversized resource layouts remain explicit scan warnings.
    """
    references, unavailable = {}, 0
    for file in context.dashboard_resources:
        try:
            text = read_regular(file, 4 * 1024 * 1024).decode('utf-8')
            textures = {}
            for header in re.findall(r'^\[ext_resource\s+[^\n]+\]$', text, re.MULTILINE):
                attrs = dict(re.findall(r'(\w+)="([^"\n]*)"', header))
                if attrs.get('type') == 'Texture2D' and attrs.get('path', '').startswith('res://'):
                    relative = attrs['path'][6:]
                    path = context.path(relative)
                    if path.suffix.lower() in IMAGE_EXTENSIONS:
                        textures[attrs.get('id')] = context.relative(path)
            blocks = re.findall(r'^\[sub_resource\s+[^\n]*type="TileSetAtlasSource"[^\n]*\]\s*\n([^\[]*)', text, re.MULTILINE)
            if re.search(r'^\[gd_resource\s+[^\n]*type="TileSetAtlasSource"', text, re.MULTILINE):
                blocks += re.findall(r'^\[resource\]\s*\n([^\[]*)', text, re.MULTILINE)
            for block in blocks:
                texture = re.search(r'^texture\s*=\s*ExtResource\("([^"\n]+)"\)', block, re.MULTILINE)
                if texture and texture.group(1) in textures:
                    references.setdefault(textures[texture.group(1)], []).append(context.relative(file))
        except (OSError, ValueError, UnicodeError):
            unavailable += 1
    return references, unavailable


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
    references, unreadable_resources = atlas_references(context)
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
            entries.append({'id': key, 'group': key, 'name': file.stem, 'kind': 'image',
                            'origin': 'project', 'path': relative, 'state': 'project_file', 'is_latest': True,
                            'modified_at': info.st_mtime_ns, 'bytes': info.st_size,
                            'format': file.suffix[1:].upper(), 'imports': [],
                            'collection_type': 'tileset' if relative in references or atlas_folder else 'image',
                            'tileset_evidence': 'godot_reference' if relative in references else 'folder' if atlas_folder else None,
                            'resource_references': sorted(set(references.get(relative, [])))})
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
                        'imports': [record], 'modified_at': 0, 'format': Path(relative).suffix[1:].upper()})
    entries.sort(key=lambda item: (-item['modified_at'], item['name'], item['id']))
    sprite_links(entries)
    project = read_regular(context.path('project.godot'), 1024 * 1024).decode('utf-8', errors='replace')
    name = re.search(r'^config/name="([^"\n]+)"', project, re.MULTILINE)
    return {'project': {'name': name.group(1) if name else context.root.name, 'directory': str(context.root)},
            'generated_at': datetime.now(timezone.utc).isoformat(), 'assets': entries,
            'imports': records, 'truncated': result['truncated'], 'unavailable': unavailable,
            'scope': 'Daydream revisions and supported project images. Existing atlas images referenced by Godot text resources or kept in tileset folders appear under Tilesets. Geometry is not inferred. Hidden/build folders are excluded.',
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
