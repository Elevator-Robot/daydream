"""Read supported Godot sprite frame data without executing Godot or project code."""

import io
import json
import math
import re

from sprite_core import digest, encoded, pillow, png_bytes, read_regular

MAX_DECODED_BYTES = 128 * 1024 * 1024
MAX_TEXTURE_PIXELS = 16 * 1024 * 1024


class UnsupportedSprite(ValueError):
    pass


class Values:
    """Small data-only subset: dictionaries, arrays, refs, strings and numbers."""
    def __init__(self, text):
        self.text, self.index, self.items = text, 0, 0

    def read(self, depth=0):
        self.items += 1
        if depth > 32 or self.items > 100000:
            raise UnsupportedSprite('Godot sprite data exceeds safe parsing limits')
        text = self.text
        while self.index < len(text) and text[self.index].isspace(): self.index += 1
        if self.index >= len(text): raise UnsupportedSprite('Incomplete Godot sprite data')
        if text.startswith('&"', self.index): self.index += 1
        char = text[self.index]
        if char == '"':
            value, end = json.JSONDecoder().raw_decode(text, self.index)
            self.index = end
            return value
        if char in '[{':
            closing, dictionary = (']', False) if char == '[' else ('}', True)
            self.index += 1
            value = {} if dictionary else []
            while True:
                while self.index < len(text) and (text[self.index].isspace() or text[self.index] == ','): self.index += 1
                if self.index >= len(text): raise UnsupportedSprite('Incomplete Godot sprite collection')
                if text[self.index] == closing:
                    self.index += 1
                    return value
                item = self.read(depth + 1)
                if dictionary:
                    if not isinstance(item, str): raise UnsupportedSprite('Unsupported Godot dictionary key')
                    while self.index < len(text) and text[self.index].isspace(): self.index += 1
                    if self.index >= len(text) or text[self.index] != ':': raise UnsupportedSprite('Malformed Godot sprite dictionary')
                    self.index += 1
                    value[item] = self.read(depth + 1)
                else: value.append(item)
        match = re.match(r'(ExtResource|SubResource|Rect2|Vector2)\(', text[self.index:])
        if match:
            self.index += len(match.group())
            arguments = []
            while True:
                while self.index < len(text) and (text[self.index].isspace() or text[self.index] == ','): self.index += 1
                if self.index >= len(text): raise UnsupportedSprite('Incomplete Godot sprite reference')
                if text[self.index] == ')': self.index += 1; break
                arguments.append(self.read(depth + 1))
            return {'type': match.group(1), 'args': arguments}
        for name, value in [('true', True), ('false', False), ('null', None)]:
            if text.startswith(name, self.index): self.index += len(name); return value
        match = re.match(r'-?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?', text[self.index:])
        if match:
            self.index += len(match.group())
            value = float(match.group())
            if not math.isfinite(value): raise UnsupportedSprite('Non-finite Godot sprite value')
            return value
        raise UnsupportedSprite('Unsupported Godot sprite value; inspect this resource in Godot')


def property_value(body, name, default=None):
    match = re.search(r'^' + re.escape(name) + r'\s*=\s*', body, re.MULTILINE)
    return Values(body[match.end():]).read() if match else default


def root_block(documents, file):
    blocks = documents.get(file, [])
    kind = next((attrs.get('type') for tag, attrs, _ in blocks if tag == 'gd_resource'), None)
    return next(((kind, body) for tag, _, body in blocks if tag == 'resource'), None)


def frame_descriptor(documents, file, value, seen=None):
    seen = set() if seen is None else seen
    if not isinstance(value, dict) or value.get('type') not in {'ExtResource', 'SubResource'} or len(value.get('args', [])) != 1:
        raise UnsupportedSprite('Unsupported sprite texture reference')
    key = (file, value['type'], str(value['args'][0]))
    if key in seen or len(seen) >= 64: raise UnsupportedSprite('Cyclic or oversized sprite texture chain')
    seen.add(key)
    tag = 'ext_resource' if value['type'] == 'ExtResource' else 'sub_resource'
    block = next(((attrs, body) for block_tag, attrs, body in documents.get(file, []) if block_tag == tag and attrs.get('id') == value['args'][0]), None)
    if not block: raise UnsupportedSprite('Sprite texture resource is not available in the scanned project data')
    attrs, body = block
    dependencies = {file}
    if tag == 'ext_resource':
        path = attrs.get('relative_path', '')
        if attrs.get('type') in {'Texture2D', 'AtlasTexture'} and path.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif', '.bmp', '.tga')):
            return {'image': path, 'box': None, 'resources': dependencies}
        block = root_block(documents, path)
        if not block: raise UnsupportedSprite('External sprite texture metadata was not scanned')
        dependencies.add(path)
        resource_type, body = block
        file = path
    else: resource_type = attrs.get('type')
    if resource_type != 'AtlasTexture': raise UnsupportedSprite('Only direct images and AtlasTexture sprite frames are supported')
    frame = frame_descriptor(documents, file, property_value(body, 'atlas'), seen)
    if frame.get('box') is not None: raise UnsupportedSprite('Nested cropped atlas textures are not supported')
    margin = property_value(body, 'margin')
    if margin and any(margin.get('args', [])): raise UnsupportedSprite('AtlasTexture margins need Godot inspection; no frame size was guessed')
    region = property_value(body, 'region')
    if region:
        if region.get('type') != 'Rect2' or len(region.get('args', [])) != 4: raise UnsupportedSprite('Unsupported atlas region')
        if any(type(number) not in (int, float) or number != int(number) for number in region['args']): raise UnsupportedSprite('Non-integer atlas regions need Godot inspection')
        frame['box'] = [int(number) for number in region['args']]
        if frame['box'][2:] == [0, 0]: frame['box'] = None
    frame['resources'] |= dependencies
    return frame


def sprite_model(documents, image_path):
    frames, clips, resources, warnings, first = {}, [], set(), [], None
    for file, blocks in documents.items():
        root = root_block(documents, file)
        for tag, attrs, body in blocks:
            resource_type = root[0] if tag == 'resource' and root else attrs.get('type')
            if resource_type != 'SpriteFrames': continue
            try:
                animations = property_value(body, 'animations', [])
                if not isinstance(animations, list): raise UnsupportedSprite('Unsupported SpriteFrames animation data')
                for clip in animations:
                    if not isinstance(clip, dict) or not isinstance(clip.get('name'), str) or not isinstance(clip.get('frames'), list): raise UnsupportedSprite('Malformed SpriteFrames clip')
                    steps, local_frames, used_resources = [], {}, {file}
                    fps = clip.get('speed', 5)
                    if type(fps) not in (int, float) or not 0 < fps <= 1000: raise UnsupportedSprite('Stopped or unsupported SpriteFrames playback speed')
                    loop_mode = clip.get('loop_mode', 1 if clip.get('loop', True) else 0)
                    if loop_mode not in (0, 1): raise UnsupportedSprite('Ping-pong SpriteFrames playback is not supported yet')
                    for step in clip['frames']:
                        if not isinstance(step, dict): raise UnsupportedSprite('Malformed SpriteFrames timeline step')
                        frame = frame_descriptor(documents, file, step.get('texture'))
                        if frame['image'] != image_path: raise UnsupportedSprite('A clip spans multiple source sheets; no frame data was guessed')
                        duration = step.get('duration', 1)
                        if type(duration) not in (int, float) or not .001 <= duration / fps <= 30: raise UnsupportedSprite('Unsupported SpriteFrames frame duration')
                        key = digest(encoded({'image': frame['image'], 'box': frame['box']}))[:16]
                        local_frames[key] = frame
                        used_resources |= frame['resources']
                        steps.append({'frame': key, 'duration': duration})
                    if not steps: continue
                    resources |= used_resources
                    frames.update(local_frames)
                    key = digest(encoded([file, attrs.get('id', 'root'), clip['name']]))[:20]
                    clips.append({'name': clip['name'], 'fps': fps, 'loop': bool(loop_mode), 'frames': steps,
                                  'duration_ms': sum(round(step['duration'] / fps * 1000) for step in steps),
                                  'media_key': 'native-motion:' + key, 'contact_key': 'native-contact:' + key,
                                  'source_resource': file})
                    first = first or steps[0]['frame']
            except (ValueError, TypeError, KeyError, AttributeError) as error:
                # This source may reference a different project image entirely.
                if image_path in str(body) or any(frame['image'] == image_path for frame in frames.values()):
                    warnings.append(str(error))
    # Static Sprite2D regions or hframes/vframes are also explicit frame metadata.
    if not first:
        for file, blocks in documents.items():
            for tag, attrs, body in blocks:
                if tag != 'node' or attrs.get('type') != 'Sprite2D': continue
                try:
                    frame = frame_descriptor(documents, file, property_value(body, 'texture'))
                    if frame['image'] != image_path: continue
                    if property_value(body, 'region_enabled', False):
                        region = property_value(body, 'region_rect')
                        if not region or region.get('type') != 'Rect2': raise UnsupportedSprite('Unsupported Sprite2D region')
                        frame['box'] = region['args']
                    else:
                        frame['grid'] = [property_value(body, 'hframes', 1), property_value(body, 'vframes', 1), property_value(body, 'frame', 0)]
                    first = digest(encoded([image_path, frame['box'], frame.get('grid')]))[:16]
                    frames[first] = frame; resources |= frame['resources']
                    break
                except (ValueError, TypeError, KeyError, AttributeError): continue
    return {'frames': frames, 'animations': clips, 'first': first, 'resources': sorted(resources), 'warnings': warnings}


def decode(context, data, model, resource_hashes):
    Image, _ = pillow()
    raw = read_regular(context.path(data['path']), 32 * 1024 * 1024)
    with Image.open(io.BytesIO(raw)) as original:
        if max(original.size) > 16384 or original.width * original.height > MAX_TEXTURE_PIXELS: raise ValueError('Sprite source exceeds the decoded pixel budget')
        image = original.convert('RGBA')
        sheet_size = list(image.size)
    frames = {}
    for key, frame in model['frames'].items():
        box = frame['box']
        if frame.get('grid'):
            cols, rows, index = frame['grid']
            bx, by, bw, bh = box if box is not None else (0, 0, image.width, image.height)
            if any(type(value) not in (int, float) or value != int(value) for value in (cols, rows, index)) or cols < 1 or rows < 1 or not 0 <= index < cols * rows or bw % cols or bh % rows:
                raise ValueError('Sprite2D grid does not divide its source image exactly')
            w, h = bw // int(cols), bh // int(rows)
            box = [bx + int(index) % int(cols) * w, by + int(index) // int(cols) * h, w, h]
        if box is None: box = [0, 0, image.width, image.height]
        if len(box) != 4 or any(type(value) not in (int, float) or value != int(value) for value in box): raise ValueError('Unsupported non-integer sprite frame')
        x, y, w, h = map(int, box)
        if min(x, y) < 0 or min(w, h) < 1 or x + w > image.width or y + h > image.height: raise ValueError('Sprite frame region extends outside its source sheet')
        if sum(item.width * item.height * 4 for item in frames.values()) + w * h * 4 > MAX_DECODED_BYTES: raise ValueError('Sprite frames exceed the decoded memory budget')
        frames[key] = image.crop((x, y, x + w, y + h))
    image.close()
    first = frames[model['first']]
    if any(frame.size != first.size for frame in frames.values()): raise ValueError('Mixed-size Godot sprite frames need editor inspection; no resizing was inferred')
    if sum(len(clip['frames']) for clip in model['animations']) * first.width * first.height * 4 > MAX_DECODED_BYTES: raise ValueError('Sprite motion exceeds the decoded preview memory budget')
    fingerprint = digest(encoded({'image_sha256': digest(raw), 'resources': resource_hashes}))
    return fingerprint, frames, sheet_size


def media_bytes(model, frames, role):
    Image, _ = pillow()
    first = frames[model['first']]
    if role in {'image', 'thumbnail'}:
        image = first.copy()
        if role == 'thumbnail': image.thumbnail((256, 192), Image.Resampling.NEAREST)
        return png_bytes(image), image.size
    if role == 'atlas':
        cols = min(8, len(frames)); rows = math.ceil(len(frames) / cols)
        if cols * first.width * rows * first.height > MAX_TEXTURE_PIXELS: raise ValueError('Sprite atlas exceeds the pixel budget')
        image = Image.new('RGBA', (cols * first.width, rows * first.height))
        for index, frame in enumerate(frames.values()): image.paste(frame, (index % cols * first.width, index // cols * first.height))
        return png_bytes(image), image.size
    clip = next((clip for clip in model['animations'] if role in {clip['media_key'], clip['contact_key']}), None)
    if not clip: raise ValueError('Unknown native sprite preview')
    if role == clip['contact_key']:
        cols = min(8, len(clip['frames'])); rows = math.ceil(len(clip['frames']) / cols)
        if cols * first.width * rows * first.height > MAX_TEXTURE_PIXELS: raise ValueError('Sprite contact sheet exceeds the pixel budget')
        image = Image.new('RGBA', (cols * first.width, rows * first.height))
        for index, step in enumerate(clip['frames']): image.paste(frames[step['frame']], (index % cols * first.width, index // cols * first.height))
        return png_bytes(image), image.size
    output = io.BytesIO()
    images = [frames[step['frame']] for step in clip['frames']]
    images[0].save(output, format='PNG', save_all=True, append_images=images[1:],
                   duration=[max(1, round(step['duration'] / clip['fps'] * 1000)) for step in clip['frames']],
                   loop=0 if clip['loop'] else 1, disposal=0, blend=0)
    return output.getvalue(), first.size
