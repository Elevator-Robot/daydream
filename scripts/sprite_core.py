"""Bounded pixel-art sources and immutable sprite revision bundles."""

import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat


SYMBOLS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
NAME = re.compile(r"[a-z][a-z0-9_-]{0,47}\Z")
HEX = re.compile(r"#[0-9a-fA-F]{6}\Z")
FILES = ("source.json", "sprite.png", "preview.png")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encoded(value):
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def pillow():
    try:
        from PIL import Image, __version__
    except ImportError as exc:
        raise ValueError("Sprite tools need optional Pillow. See docs/SPRITES.md; nothing was installed automatically.") from exc
    return Image, __version__


def validate_source(source):
    expected = {"schema_version", "name", "width", "height", "palette", "pixels"}
    if not isinstance(source, dict) or set(source) != expected:
        raise ValueError("Sprite source requires exactly schema_version, name, width, height, palette, pixels")
    if type(source["schema_version"]) is not int or source["schema_version"] != 1:
        raise ValueError("Unsupported sprite schema_version")
    if not isinstance(source["name"], str) or not NAME.fullmatch(source["name"]):
        raise ValueError("Sprite name must be a lowercase asset slug (1–48 characters)")
    width, height = source["width"], source["height"]
    if any(type(value) is not int or not 1 <= value <= 256 for value in (width, height)):
        raise ValueError("Sprite dimensions must be integers from 1 to 256")
    palette = source["palette"]
    if not isinstance(palette, dict) or not 1 <= len(palette) <= 32:
        raise ValueError("Sprite palette must contain 1–32 colors")
    for symbol, color in palette.items():
        if not isinstance(symbol, str) or len(symbol) != 1 or symbol not in SYMBOLS or not isinstance(color, str) or not HEX.fullmatch(color):
            raise ValueError("Palette keys must be single letters/digits and colors must be #RRGGBB; '.' is reserved for transparency")
    rows = source["pixels"]
    if not isinstance(rows, list) or len(rows) != height:
        raise ValueError("Pixel row count must equal height")
    if any(not isinstance(row, str) or len(row) != width or any(ch not in palette and ch != "." for ch in row) for row in rows):
        raise ValueError("Each pixel row must match width and use declared palette symbols or '.'")
    return source


def read_regular(path, limit=8 * 1024 * 1024, *, dir_fd=None):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError(f"Refusing non-regular or oversized file: {path}")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"File is too large: {path}")
        return data
    finally:
        os.close(fd)


def read_json(path):
    return json.loads(read_regular(path, 1024 * 1024))


def image_from_source(source):
    validate_source(source)
    Image, _ = pillow()
    palette = {symbol: tuple(bytes.fromhex(color[1:])) + (255,) for symbol, color in source["palette"].items()}
    image = Image.new("RGBA", (source["width"], source["height"]))
    image.putdata([palette.get(ch, (0, 0, 0, 0)) for row in source["pixels"] for ch in row])
    return image


def png_bytes(image):
    output = io.BytesIO()
    image.save(output, format="PNG", optimize=False)
    return output.getvalue()


def open_image(data):
    Image, _ = pillow()
    try:
        return Image.open(io.BytesIO(data))
    except Image.DecompressionBombError as exc:
        raise ValueError("Image dimensions exceed safe sprite/preview limits") from exc


def preview(image, scale=8):
    if type(scale) is not int or not 1 <= scale <= 8:
        raise ValueError("Pixel preview scale must be an integer from 1 to 8")
    Image, _ = pillow()
    enlarged = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    background = Image.new("RGBA", enlarged.size)
    background.putdata([(42, 47, 59, 255) if (x // scale + y // scale) % 2 else (66, 73, 88, 255)
                        for y in range(enlarged.height) for x in range(enlarged.width)])
    return Image.alpha_composite(background, enlarged)


def source_from_png(path, name):
    data = read_regular(path)
    with open_image(data) as original:
        if original.format != "PNG" or getattr(original, "n_frames", 1) != 1 or not all(1 <= value <= 256 for value in original.size):
            raise ValueError("Expected one PNG frame, at most 256×256")
        image = original.convert("RGBA")
    rgba = image.tobytes()
    pixels = [tuple(rgba[index:index + 4]) for index in range(0, len(rgba), 4)]
    if any(pixel[3] not in (0, 255) for pixel in pixels):
        raise ValueError("This pixel-art workflow requires binary transparency (alpha 0 or 255)")
    colors = sorted({pixel[:3] for pixel in pixels if pixel[3]})
    if not 1 <= len(colors) <= 32:
        raise ValueError("PNG must use 1–32 opaque colors")
    symbols = {color: SYMBOLS[index] for index, color in enumerate(colors)}
    rows = ["".join(symbols[pixel[:3]] if pixel[3] else "." for pixel in pixels[y * image.width:(y + 1) * image.width]) for y in range(image.height)]
    source = {"schema_version": 1, "name": name, "width": image.width, "height": image.height,
              "palette": {symbol: "#" + bytes(color).hex() for color, symbol in symbols.items()}, "pixels": rows}
    return validate_source(source), {"method": "png-import", "input_sha256": digest(data), "license": None}


def edit_source(source, patch):
    source = json.loads(json.dumps(validate_source(source)))
    if not isinstance(patch, dict) or set(patch) != {"schema_version", "operations"} or type(patch["schema_version"]) is not int or patch["schema_version"] != 1:
        raise ValueError("Edit patch requires schema_version: 1 and operations")
    operations = patch["operations"]
    if not isinstance(operations, list) or not 1 <= len(operations) <= 1024:
        raise ValueError("Expected 1–1024 edit operations")
    width, height = source["width"], source["height"]
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Edit operations must be objects")
        kind = operation.get("op")
        if not isinstance(kind, str):
            raise ValueError("Edit operation name must be a string")
        if kind == "recolor" and set(operation) == {"op", "symbol", "color"}:
            if not isinstance(operation["symbol"], str) or operation["symbol"] not in source["palette"] or not isinstance(operation["color"], str) or not HEX.fullmatch(operation["color"]):
                raise ValueError("Recolor requires an existing palette symbol and #RRGGBB color")
            source["palette"][operation["symbol"]] = operation["color"].lower()
        elif kind == "mirror" and set(operation) == {"op", "axis"} and isinstance(operation["axis"], str) and operation["axis"] in {"horizontal", "vertical"}:
            source["pixels"] = [row[::-1] for row in source["pixels"]] if operation["axis"] == "horizontal" else source["pixels"][::-1]
        elif kind in {"paint", "rect"}:
            keys = {"op", "x", "y", "symbol"} if kind == "paint" else {"op", "box", "symbol"}
            if set(operation) != keys or not isinstance(operation["symbol"], str) or operation["symbol"] not in {*source["palette"], "."}:
                raise ValueError("Paint/rect requires a declared symbol or '.'")
            box = [operation["x"], operation["y"], operation["x"], operation["y"]] if kind == "paint" else operation["box"]
            if not isinstance(box, list) or len(box) != 4 or any(type(value) is not int for value in box):
                raise ValueError("Expected integer pixel coordinates")
            x0, y0, x1, y1 = box
            if not (0 <= x0 <= x1 < width and 0 <= y0 <= y1 < height):
                raise ValueError("Edit coordinates are outside the sprite")
            for y in range(y0, y1 + 1):
                row = source["pixels"][y]
                source["pixels"][y] = row[:x0] + operation["symbol"] * (x1 - x0 + 1) + row[x1 + 1:]
        else:
            raise ValueError("Unknown or malformed edit operation")
    return validate_source(source)


def make_revision(source, provenance):
    source = validate_source(source)
    image = image_from_source(source)
    files = {"source.json": encoded(source), "sprite.png": png_bytes(image), "preview.png": png_bytes(preview(image))}
    _, version = pillow()
    manifest = {"schema_version": 1, "kind": "sprite", "name": source["name"],
                "width": source["width"], "height": source["height"],
                "files": {name: digest(data) for name, data in files.items()},
                "generator": {"tool": "daydream-sprites", "pillow": version}, "provenance": provenance}
    files["manifest.json"] = encoded(manifest)
    files[".gdignore"] = b""
    return files


def load_revision(path):
    path = Path(path).expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        files = {name: read_regular(name, 8 * 1024 * 1024 if name == "preview.png" else 1024 * 1024, dir_fd=fd)
                 for name in (*FILES, "manifest.json", ".gdignore")}
    finally:
        os.close(fd)
    manifest = json.loads(files["manifest.json"])
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or manifest.get("kind") != "sprite" or not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != set(FILES):
        raise ValueError("Unsupported sprite manifest")
    if any(manifest["files"][name] != digest(files[name]) for name in FILES):
        raise ValueError("Revision hash mismatch; do not reuse approval after editing files")
    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict) or provenance.get("method") not in ("pixel-spec", "png-import", "edit") or not (provenance.get("license") is None or isinstance(provenance["license"], str)):
        raise ValueError("Invalid sprite provenance record")
    generator = manifest.get("generator")
    if not isinstance(generator, dict) or generator.get("tool") != "daydream-sprites" or not isinstance(generator.get("pillow"), str):
        raise ValueError("Invalid sprite generator record")
    source = validate_source(json.loads(files["source.json"]))
    if any(manifest.get(key) != source[key] for key in ("name", "width", "height")) or any(type(manifest.get(key)) is not int for key in ("width", "height")):
        raise ValueError("Manifest does not match source dimensions/name")
    with open_image(files["sprite.png"]) as image:
        if image.format != "PNG" or image.size != (source["width"], source["height"]) or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Revision PNG does not match source")
        if image.convert("RGBA").tobytes() != image_from_source(source).tobytes():
            raise ValueError("Revision pixels do not match editable source")
    with open_image(files["preview.png"]) as image:
        if image.format != "PNG" or image.size != (source["width"] * 8, source["height"] * 8) or getattr(image, "n_frames", 1) != 1:
            raise ValueError("Revision preview has the wrong format or dimensions")
        if image.convert("RGBA").tobytes() != preview(image_from_source(source)).tobytes():
            raise ValueError("Revision preview does not depict the editable sprite")
    return {"path": path, "source": source, "manifest": manifest, "files": files, "revision_hash": digest(files["manifest.json"])}
