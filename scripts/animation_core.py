"""Bounded sprite animation sources and motion/contact-sheet previews."""

import copy
import html
import io
import json
import math
import os
from pathlib import Path

from sprite_core import NAME, digest, edit_source, encoded, image_from_source
from sprite_core import open_image, pillow, png_bytes, preview, read_regular, validate_source as validate_sprite


KIND = "sprite_animation"


def number(value):
    return type(value) in (int, float) and abs(value) <= 1000000 and math.isfinite(value)


def validate_source(source):
    keys = {"schema_version", "name", "width", "height", "pivot", "frames", "animations", "default_animation"}
    if not isinstance(source, dict) or set(source) != keys or type(source["schema_version"]) is not int or source["schema_version"] != 1:
        raise ValueError("Unsupported animation source schema")
    if not isinstance(source["name"], str) or not NAME.fullmatch(source["name"]):
        raise ValueError("Animation asset name must be a lowercase slug")
    width, height = source["width"], source["height"]
    if any(type(value) is not int or not 1 <= value <= 128 for value in (width, height)):
        raise ValueError("Animation canvas must be 1–128 pixels per dimension")
    pivot = source["pivot"]
    if not isinstance(pivot, list) or len(pivot) != 2 or any(type(value) is not int for value in pivot) or not (0 <= pivot[0] <= width and 0 <= pivot[1] <= height):
        raise ValueError("Animation pivot must be two integer coordinates inside/on the canvas")
    frames = source["frames"]
    if not isinstance(frames, list) or not 1 <= len(frames) <= 32:
        raise ValueError("Expected 1–32 unique animation frames")
    ids, palette = set(), None
    for frame in frames:
        if not isinstance(frame, dict) or set(frame) != {"id", "source"} or not isinstance(frame["id"], str) or not NAME.fullmatch(frame["id"]) or frame["id"] in ids:
            raise ValueError("Frame IDs must be unique lowercase slugs")
        ids.add(frame["id"])
        sprite = validate_sprite(frame["source"])
        if (sprite["width"], sprite["height"]) != (width, height):
            raise ValueError("Every frame must use the same canvas; implicit resizing is forbidden")
        if palette is not None and sprite["palette"] != palette:
            raise ValueError("Every frame must declare the same palette")
        palette = sprite["palette"]
    animations = source["animations"]
    if not isinstance(animations, list) or not 1 <= len(animations) <= 8:
        raise ValueError("Expected 1–8 named animations")
    names, total_steps = set(), 0
    for animation in animations:
        if not isinstance(animation, dict) or set(animation) != {"name", "fps", "loop", "frames"} or not isinstance(animation["name"], str) or not NAME.fullmatch(animation["name"]) or animation["name"] in names:
            raise ValueError("Animation names must be unique lowercase slugs")
        names.add(animation["name"])
        if not number(animation["fps"]) or not 1 <= animation["fps"] <= 30 or type(animation["loop"]) is not bool:
            raise ValueError("Animation FPS must be finite (1–30) and loop must be boolean")
        steps = animation["frames"]
        if not isinstance(steps, list) or not 1 <= len(steps) <= 64:
            raise ValueError("Expected 1–64 ordered timeline steps per animation")
        total_steps += len(steps)
        seconds = 0
        for step in steps:
            if not isinstance(step, dict) or set(step) != {"frame", "duration"} or not isinstance(step["frame"], str) or step["frame"] not in ids or not number(step["duration"]) or step["duration"] <= 0:
                raise ValueError("Timeline steps need a known frame ID and positive finite relative duration")
            duration = step["duration"] / animation["fps"]
            if not 0.02 <= duration <= 5:
                raise ValueError("Each frame must display for 20–5000 ms")
            seconds += duration
        if seconds > 30:
            raise ValueError("Animation clips must not exceed 30 seconds")
    if total_steps > 128 or not isinstance(source["default_animation"], str) or source["default_animation"] not in names:
        raise ValueError("Expected at most 128 total steps and an existing default animation")
    return source


def source_from_recipe(base, recipe):
    validate_sprite(base)
    if not isinstance(recipe, dict) or set(recipe) != {"schema_version", "name", "pivot", "frames", "animations", "default_animation"} or type(recipe["schema_version"]) is not int or recipe["schema_version"] != 1:
        raise ValueError("Unsupported animation recipe")
    if not isinstance(recipe["frames"], list) or not 1 <= len(recipe["frames"]) <= 32:
        raise ValueError("Recipe requires 1–32 frame definitions")
    frames = []
    for frame in recipe["frames"]:
        if not isinstance(frame, dict) or set(frame) not in ({"id"}, {"id", "patch"}, {"id", "pixels"}):
            raise ValueError("Recipe frames need id and optionally patch or pixels")
        sprite = copy.deepcopy(base)
        if "patch" in frame:
            sprite = edit_source(sprite, frame["patch"])
        elif "pixels" in frame:
            sprite["pixels"] = copy.deepcopy(frame["pixels"])
        frames.append({"id": frame["id"], "source": sprite})
    return validate_source({"schema_version": 1, "name": recipe["name"], "width": base["width"], "height": base["height"],
                            "pivot": copy.deepcopy(recipe["pivot"]), "frames": frames,
                            "animations": copy.deepcopy(recipe["animations"]), "default_animation": recipe["default_animation"]})


def edit_animation(source, patch):
    source = copy.deepcopy(validate_source(source))
    if not isinstance(patch, dict) or set(patch) != {"schema_version", "operations"} or type(patch["schema_version"]) is not int or patch["schema_version"] != 1 or not isinstance(patch["operations"], list) or not 1 <= len(patch["operations"]) <= 128:
        raise ValueError("Animation edits require schema_version: 1 and 1–128 operations")
    for operation in patch["operations"]:
        if not isinstance(operation, dict) or not isinstance(operation.get("op"), str):
            raise ValueError("Malformed animation edit")
        kind = operation["op"]
        if kind == "frame" and set(operation) == {"op", "id", "patch"}:
            frame = next((frame for frame in source["frames"] if frame["id"] == operation["id"]), None)
            if frame is None:
                raise ValueError("Frame edit references an unknown ID")
            frame["source"] = edit_source(frame["source"], operation["patch"])
        elif kind == "recolor" and set(operation) == {"op", "symbol", "color"}:
            for frame in source["frames"]:
                frame["source"] = edit_source(frame["source"], {"schema_version": 1, "operations": [operation]})
        elif kind == "animation" and set(operation) == {"op", "value"} and isinstance(operation["value"], dict):
            value = operation["value"]
            index = next((index for index, item in enumerate(source["animations"]) if item["name"] == value.get("name")), None)
            if index is None:
                source["animations"].append(copy.deepcopy(value))
            else:
                source["animations"][index] = copy.deepcopy(value)
        elif kind == "pivot" and set(operation) == {"op", "value"}:
            source["pivot"] = copy.deepcopy(operation["value"])
        elif kind == "default" and set(operation) == {"op", "animation"}:
            source["default_animation"] = operation["animation"]
        else:
            raise ValueError("Unknown or malformed animation edit")
    return validate_source(source)


def artifact_names(source):
    return {"source.json", "spritesheet.png", "preview.html"} | {
        animation["name"] + suffix for animation in source["animations"] for suffix in (".motion.png", ".contact.png")
    }


def sheet(source):
    Image, _ = pillow()
    columns = min(8, len(source["frames"]))
    rows = math.ceil(len(source["frames"]) / columns)
    image = Image.new("RGBA", (columns * source["width"], rows * source["height"]))
    for index, frame in enumerate(source["frames"]):
        image.paste(image_from_source(frame["source"]), (index % columns * source["width"], index // columns * source["height"]))
    return image


def motion_frames(source, animation):
    lookup = {frame["id"]: frame["source"] for frame in source["frames"]}
    frames, durations = [], []
    for step in animation["frames"]:
        image = preview(image_from_source(lookup[step["frame"]]), scale=4)
        duration = round(step["duration"] / animation["fps"] * 1000)
        if frames and image.tobytes() == frames[-1].tobytes():
            durations[-1] += duration
        else:
            frames.append(image)
            durations.append(duration)
    return frames, durations


def motion_png(source, animation):
    frames, durations = motion_frames(source, animation)
    output = io.BytesIO()
    frames[0].save(output, format="PNG", save_all=True, append_images=frames[1:], duration=durations,
                   loop=0 if animation["loop"] else 1, disposal=0, blend=0, optimize=False)
    return output.getvalue()


def contact_sheet(source, animation):
    Image, _ = pillow()
    from PIL import ImageDraw
    count = len(animation["frames"])
    scale = 2
    while True:
        cell_width, cell_height = max(128, source["width"] * scale + 16), source["height"] * scale + 36
        columns = min(8, max(1, 2048 // cell_width), count)
        rows = math.ceil(count / columns)
        if rows * cell_height <= 2048:
            break
        scale -= 1
    result = Image.new("RGBA", (columns * cell_width, rows * cell_height), (28, 32, 42, 255))
    draw = ImageDraw.Draw(result)
    lookup = {frame["id"]: frame["source"] for frame in source["frames"]}
    for index, step in enumerate(animation["frames"]):
        x, y = index % columns * cell_width + 8, index // columns * cell_height + 4
        image = preview(image_from_source(lookup[step["frame"]]), scale=scale)
        result.paste(image, (x, y))
        px, py = x + source["pivot"][0] * scale, y + source["pivot"][1] * scale
        draw.line((px - 3, py, px + 3, py), fill="#ffd166", width=1)
        draw.line((px, py - 3, px, py + 3), fill="#ffd166", width=1)
        draw.text((x, y + image.height + 4), f'{index + 1:02} {step["frame"][:12]}', fill="#f0f0f0")
        draw.text((x, y + image.height + 16), f'{round(step["duration"] / animation["fps"] * 1000)} ms', fill="#b7c3d5")
    return result


def viewer(source):
    sections = []
    for animation in source["animations"]:
        name = html.escape(animation["name"])
        steps = "".join(f'<li>{html.escape(step["frame"])}: {step["duration"] / animation["fps"] * 1000:.2f} ms</li>' for step in animation["frames"])
        sections.append(f'<section><h2>{name}</h2><p>{animation["fps"]} FPS · loop: {animation["loop"]}</p>'
                        f'<img src="{name}.motion.png" alt="Motion preview of {name}"><details><summary>Frames and timing</summary>'
                        f'<img src="{name}.contact.png" alt="Ordered frames with pivot markers"><ol>{steps}</ol></details></section>')
    return ('<!doctype html><meta charset="utf-8"><title>' + html.escape(source["name"]) + '</title>'
            '<style>body{background:#1c202a;color:#f0f0f0;font:16px system-ui;margin:2rem}img{image-rendering:pixelated;max-width:100%}section{margin:2rem 0}li{margin:.3rem 0}</style>'
            '<h1>' + html.escape(source["name"]) + '</h1><p>Local preview. Reload to replay a non-looping clip. Yellow crosses mark the shared pivot on contact sheets.</p>'
            + "".join(sections)).encode("utf-8")


def make_revision(source, provenance):
    validate_source(source)
    files = {"source.json": encoded(source), "spritesheet.png": png_bytes(sheet(source)), "preview.html": viewer(source)}
    for animation in source["animations"]:
        files[animation["name"] + ".motion.png"] = motion_png(source, animation)
        files[animation["name"] + ".contact.png"] = png_bytes(contact_sheet(source, animation))
    if any(len(data) > 16 * 1024 * 1024 for data in files.values()) or sum(map(len, files.values())) > 32 * 1024 * 1024:
        raise ValueError("Animation preview bundle exceeds its size limit")
    _, version = pillow()
    files["manifest.json"] = encoded({"schema_version": 1, "kind": KIND, "name": source["name"], "width": source["width"], "height": source["height"],
                                      "files": {name: digest(data) for name, data in files.items()},
                                      "generator": {"tool": "daydream-animations", "pillow": version}, "provenance": provenance})
    files[".gdignore"] = b""
    return files


def load_revision(path):
    path = Path(path).expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        source_data = read_regular("source.json", 1024 * 1024, dir_fd=fd)
        source = validate_source(json.loads(source_data))
        names = artifact_names(source)
        manifest_data = read_regular("manifest.json", 1024 * 1024, dir_fd=fd)
        manifest = json.loads(manifest_data)
        if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or manifest.get("kind") != KIND or not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != names:
            raise ValueError("Unsupported animation manifest")
        files, remaining = {}, 32 * 1024 * 1024
        for name in sorted(names):
            data = read_regular(name, min(16 * 1024 * 1024, remaining), dir_fd=fd)
            files[name] = data
            remaining -= len(data)
        read_regular(".gdignore", 1024, dir_fd=fd)
    finally:
        os.close(fd)
    if sum(map(len, files.values())) > 32 * 1024 * 1024 or any(digest(files[name]) != manifest["files"][name] for name in names):
        raise ValueError("Animation revision hash mismatch or oversized bundle")
    if files["source.json"] != source_data or any(type(manifest.get(key)) is not int or manifest[key] != source[key] for key in ("width", "height")) or manifest.get("name") != source["name"]:
        raise ValueError("Animation manifest does not match source")
    provenance = manifest.get("provenance")
    if not isinstance(manifest.get("generator"), dict) or manifest["generator"].get("tool") != "daydream-animations" or not isinstance(manifest["generator"].get("pillow"), str) or not isinstance(provenance, dict) or provenance.get("method") not in ("animation-recipe", "animation-edit", "animation-source") or not (provenance.get("license") is None or isinstance(provenance["license"], str)):
        raise ValueError("Invalid animation provenance/generator record")
    with open_image(files["spritesheet.png"]) as image:
        expected = sheet(source)
        if image.format != "PNG" or getattr(image, "n_frames", 1) != 1 or image.size != expected.size or image.convert("RGBA").tobytes() != expected.tobytes():
            raise ValueError("Spritesheet does not match animation source")
    if files["preview.html"] != viewer(source):
        raise ValueError("Animation viewer must contain only the generated local preview")
    for animation in source["animations"]:
        with open_image(files[animation["name"] + ".contact.png"]) as image:
            expected = contact_sheet(source, animation)
            if image.format != "PNG" or getattr(image, "n_frames", 1) != 1 or image.size != expected.size or image.convert("RGBA").tobytes() != expected.tobytes():
                raise ValueError("Contact sheet does not depict the ordered animation frames")
        frames, durations = motion_frames(source, animation)
        with open_image(files[animation["name"] + ".motion.png"]) as image:
            # Pillow emits an ordinary PNG when every visual frame is identical.
            # There is no visible motion to encode; source/Godot timing is kept.
            static = len(frames) == 1 and image.n_frames == 1 and "loop" not in image.info and "duration" not in image.info
            if image.format != "PNG" or image.size != frames[0].size or image.n_frames != len(frames) or (not static and image.info.get("loop") != (0 if animation["loop"] else 1)):
                raise ValueError("Motion preview frame count, canvas, or loop does not match")
            for index, expected in enumerate(frames):
                image.seek(index)
                if image.convert("RGBA").tobytes() != expected.tobytes() or (not static and abs(image.info.get("duration", 0) - durations[index]) > 1):
                    raise ValueError("Motion preview pixels/timing do not match the animation")
    files["manifest.json"] = manifest_data
    return {"path": path, "source": source, "manifest": manifest, "files": files, "revision_hash": digest(manifest_data)}
