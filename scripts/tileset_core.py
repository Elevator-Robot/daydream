"""Bounded editable environment tiles, terrain transitions and honest seam evidence."""

import copy
import html
import json
import os
import itertools
from pathlib import Path

import sprite_core as sprite
import collision_core as collision

KIND = "tileset"
ARTIFACTS = {"source.json", "atlas.png", "preview.png", "layout.png", "seams.json", "preview.html"}


def validate_source(source):
    keys = {"schema_version", "name", "terrains", "tiles", "cells", "collision_layer", "collision_mask"}
    if not isinstance(source, dict) or set(source) != keys or type(source["schema_version"]) is not int or source["schema_version"] != 1:
        raise ValueError("Tileset source requires the documented version-1 fields")
    if not isinstance(source["name"], str) or not sprite.NAME.fullmatch(source["name"]):
        raise ValueError("Tileset name must be a lowercase slug")
    terrains, tiles, cells = source["terrains"], source["tiles"], source["cells"]
    if not isinstance(terrains, list) or not 1 <= len(terrains) <= 8 or any(not isinstance(name, str) or not sprite.NAME.fullmatch(name) for name in terrains) or len(set(terrains)) != len(terrains):
        raise ValueError("Use 1–8 distinct terrain slugs")
    if not isinstance(tiles, list) or not 1 <= len(tiles) <= 192:
        raise ValueError("Use 1–192 environment tiles")
    ids, canvas, palette = set(), None, None
    for tile in tiles:
        if not isinstance(tile, dict) or not {"id", "source", "terrain", "corners", "solid"}.issubset(tile) or set(tile) - {"id", "source", "terrain", "corners", "solid", "collisions"}:
            raise ValueError("Each tile needs id, source, terrain, corners, solid and optional collisions")
        name = tile["id"]
        if not isinstance(name, str) or not sprite.NAME.fullmatch(name) or name in ids:
            raise ValueError("Tile IDs must be distinct lowercase slugs")
        ids.add(name)
        value = sprite.validate_source(tile["source"])
        size = (value["width"], value["height"])
        if any(not 2 <= dimension <= 64 for dimension in size):
            raise ValueError("Tile dimensions must be 2–64 pixels")
        if canvas is not None and (canvas != size or palette != value["palette"]):
            raise ValueError("All tiles must share the same canvas and palette")
        canvas, palette = size, value["palette"]
        if type(tile["terrain"]) is not int or not 0 <= tile["terrain"] < len(terrains) or type(tile["solid"]) is not bool:
            raise ValueError("Invalid tile center terrain or solid flag")
        if "collisions" in tile:
            if tile["solid"]:
                raise ValueError("Explicit collision polygons require solid:false; do not combine legacy full-tile and custom shapes")
            collision.validate_polygons(tile["collisions"], *size)
        if not isinstance(tile["corners"], list) or len(tile["corners"]) != 4 or any(type(bit) is not int or not -1 <= bit < len(terrains) for bit in tile["corners"]):
            raise ValueError("Corners must be terrain indices ordered top-left, top-right, bottom-right, bottom-left")
    for key in ("collision_layer", "collision_mask"):
        if type(source[key]) is not int or not 0 <= source[key] <= 0xffffffff:
            raise ValueError("Collision layer/mask must be unsigned 32-bit bitmasks")
    if not isinstance(cells, list) or len(cells) > 1024:
        raise ValueError("Layout supports up to 1024 explicitly placed cells")
    positions = set()
    for cell in cells:
        if not isinstance(cell, dict) or set(cell) != {"x", "y", "tile"} or any(type(cell[axis]) is not int or not 0 <= cell[axis] < 64 for axis in ("x", "y")) or not isinstance(cell["tile"], str) or cell["tile"] not in ids:
            raise ValueError("Cells need a known tile ID and integer coordinates in 0–63")
        position = (cell["x"], cell["y"])
        if position in positions:
            raise ValueError("Layout cells cannot overlap")
        positions.add(position)
    if len(sprite.encoded(source)) > 1024 * 1024:
        raise ValueError("Tileset source exceeds 1 MiB")
    return copy.deepcopy(source)


def rgba_rows(source):
    palette = {key: tuple(bytes.fromhex(value[1:])) + (255,) for key, value in source["palette"].items()}
    return [[palette.get(symbol, (0, 0, 0, 0)) for symbol in row] for row in source["pixels"]]


def seams(source):
    """Exact boundary equality is useful evidence, not perceptual seamlessness."""
    pixels = {tile["id"]: rgba_rows(tile["source"]) for tile in source["tiles"]}
    checks, mismatches, missing, missing_count = 0, [], [], 0
    for a in source["tiles"]:
        for b in source["tiles"]:
            for axis in ("right", "bottom"):
                ac, bc = a["corners"], b["corners"]
                compatible = (ac[1], ac[2]) == (bc[0], bc[3]) if axis == "right" else (ac[3], ac[2]) == (bc[0], bc[1])
                if not compatible:
                    continue
                checks += 1
                ap, bp = pixels[a["id"]], pixels[b["id"]]
                count = sum(row_a[-1] != row_b[0] for row_a, row_b in zip(ap, bp)) if axis == "right" else sum(x != y for x, y in zip(ap[-1], bp[0]))
                if count:
                    mismatches.append({"a": a["id"], "b": b["id"], "axis": axis, "different_pixels": count})
    for terrain in range(len(source["terrains"])):
        available = {tuple(tile["corners"]) for tile in source["tiles"] if tile["terrain"] == terrain}
        for corners in itertools.product(range(-1, len(source["terrains"])), repeat=4):
            if corners not in available:
                missing_count += 1
                if len(missing) < 128:
                    missing.append({"terrain": terrain, "corners": list(corners)})
    by_id = {tile["id"]: tile for tile in source["tiles"]}
    grid = {(cell["x"], cell["y"]): cell["tile"] for cell in source["cells"]}
    layout_errors = []
    for (x, y), name in grid.items():
        a = by_id[name]["corners"]
        for axis, position in (("right", (x + 1, y)), ("bottom", (x, y + 1))):
            if position not in grid:
                continue
            b = by_id[grid[position]]["corners"]
            if ((a[1], a[2]) != (b[0], b[3]) if axis == "right" else (a[3], a[2]) != (b[0], b[1])):
                layout_errors.append({"x": x, "y": y, "axis": axis})
    return {"metric": "exact_rgba_boundary_equality", "compatible_pairs_checked": checks,
            "mismatch_count": len(mismatches), "mismatches": mismatches[:128],
            "missing_corner_pattern_count": missing_count, "missing_corner_patterns": missing, "layout_terrain_mismatches": layout_errors,
            "visual_review_required": True}


def transitions(background, foreground, name, terrains, solid_foreground=False):
    """162 Wang tiles: two centers and all floor/wall/empty corner combinations."""
    if not isinstance(terrains, list) or len(terrains) != 2 or any(not isinstance(value, str) or not sprite.NAME.fullmatch(value) for value in terrains) or terrains[0] == terrains[1] or type(solid_foreground) is not bool:
        raise ValueError("Transitions require two distinct terrain slugs and a Boolean solid_foreground flag")
    a, b = sprite.validate_source(background), sprite.validate_source(foreground)
    if (a["width"], a["height"], a["palette"]) != (b["width"], b["height"], b["palette"]):
        raise ValueError("Transition seeds must share canvas and palette")
    w, h = a["width"], a["height"]
    if not 4 <= w <= 32 or not 4 <= h <= 32:
        raise ValueError("Transition seeds must be 4–32 pixels")
    for seed in (a, b):
        rows = rgba_rows(seed)
        if any(row[0] != row[-1] for row in rows) or rows[0] != rows[-1]:
            raise ValueError("Transition seeds must have matching opposite RGBA edges; edit the seed before generating")
    tiles = []
    patterns = [(center, f"tile-{center}-{mask:02d}", [(mask >> bit) & 1 for bit in range(4)]) for center in range(2) for mask in range(16)]
    patterns += [(center, f"edge-{center}-{index:02d}", list(corners)) for center in range(2)
                 for index, corners in enumerate(itertools.product((-1, 0, 1), repeat=4)) if -1 in corners]
    for center, tile_id, corners in patterns:
        rows = []
        for y in range(h):
            row = ""
            v = y / (h - 1)
            for x in range(w):
                u = x / (w - 1)
                # Boundary pixels depend only on shared corner labels. The
                # center contributes only inside, so compatible edges match.
                weight = 1 - 2 * max(abs(u - .5), abs(v - .5))
                weights = [(1-u)*(1-v), u*(1-v), u*v, (1-u)*v]
                scores = {terrain: sum(value for corner, value in zip(corners, weights) if corner == terrain) * (1-weight) + (weight if center == terrain else 0) for terrain in (-1, 0, 1)}
                chosen = max((-1, 0, 1), key=lambda terrain: (scores[terrain], terrain))
                row += "." if chosen == -1 else (a, b)[chosen]["pixels"][y][x]
            rows.append(row)
        tile_source = {**copy.deepcopy(a), "name": tile_id, "pixels": rows}
        tiles.append({"id": tile_source["name"], "source": tile_source, "terrain": center,
                      "corners": corners, "solid": bool(center and solid_foreground)})
    # A small repeated island has real compatible transitions, not an arbitrary atlas grid.
    vertices = [[int(1 <= x <= 3 and 1 <= y <= 3) for x in range(6)] for y in range(6)]
    cells = []
    for y in range(5):
        for x in range(5):
            bits = [vertices[y][x], vertices[y][x+1], vertices[y+1][x+1], vertices[y+1][x]]
            center = int(sum(bits) >= 2)
            mask = sum(bit << index for index, bit in enumerate(bits))
            cells.append({"x": x, "y": y, "tile": f"tile-{center}-{mask:02d}"})
    return validate_source({"schema_version": 1, "name": name, "terrains": terrains, "tiles": tiles,
                            "cells": cells, "collision_layer": 1, "collision_mask": 1})


def artifact_names(source):
    return ARTIFACTS | ({"collisions.png"} if any("collisions" in tile for tile in source["tiles"]) else set())


def images(source):
    Image, _ = sprite.pillow()
    from PIL import ImageDraw
    first = source["tiles"][0]["source"]
    w, h = first["width"], first["height"]
    columns = min(8, len(source["tiles"]))
    cell_width = max(w+2, 24)
    atlas = Image.new("RGBA", (columns*w, ((len(source["tiles"])+columns-1)//columns)*h))
    preview = Image.new("RGBA", (columns*cell_width, ((len(source["tiles"])+columns-1)//columns)*(h+12)), "#252934")
    rendered = {}
    overlays = {}
    has_geometry = "collisions.png" in artifact_names(source)
    for index, tile in enumerate(source["tiles"]):
        image = Image.new("RGBA", (w, h))
        image.putdata([pixel for row in rgba_rows(tile["source"]) for pixel in row])
        rendered[tile["id"]] = image
        atlas.paste(image, (index % columns*w, index // columns*h))
        x, y = index % columns*cell_width, index // columns*(h+12)
        preview.paste(image, (x, y))
        draw = ImageDraw.Draw(preview)
        draw.text((x, y+h), str(index), fill="white")
        if tile["solid"]:
            draw.rectangle((x, y, x+w-1, y+h-1), outline="#ffcc00")
        if "collisions" in tile:
            for polygon in collision.effective_polygons(tile):
                points = [(x + min(w-1, px), y + min(h-1, py)) for px, py in polygon["points"]]
                draw.line(points + points[:1], fill="#00e5ff" if polygon["one_way"] else "#ffcc00", width=1)
        if has_geometry:
            overlay = Image.new("RGBA", (w, h))
            geometry = ImageDraw.Draw(overlay)
            for polygon in collision.effective_polygons(tile):
                points = [(min(w-1, px), min(h-1, py)) for px, py in polygon["points"]]
                geometry.polygon(points, fill=(0, 229, 255, 80) if polygon["one_way"] else (255, 204, 0, 80))
                geometry.line(points + points[:1], fill="#00e5ff" if polygon["one_way"] else "#ffcc00", width=1)
            overlays[tile["id"]] = Image.alpha_composite(image, overlay)
    max_x = max((cell["x"] for cell in source["cells"]), default=0) + 1
    max_y = max((cell["y"] for cell in source["cells"]), default=0) + 1
    layout = Image.new("RGBA", (max_x*w, max_y*h))
    collision_layout = Image.new("RGBA", layout.size) if overlays else None
    for cell in source["cells"]:
        layout.paste(rendered[cell["tile"]], (cell["x"]*w, cell["y"]*h))
        if collision_layout is not None:
            collision_layout.paste(overlays[cell["tile"]], (cell["x"]*w, cell["y"]*h))
    # Enlarge only within 1024 pixels; never shrink away native tile pixels.
    scale = max(1, min(4, 1024 // max(preview.size)))
    preview = preview.resize((preview.width*scale, preview.height*scale), Image.Resampling.NEAREST)
    result = {"atlas.png": atlas, "preview.png": preview, "layout.png": layout}
    if collision_layout is not None:
        result["collisions.png"] = collision_layout
    return result


def viewer(source, report):
    legacy = ('<!doctype html><meta charset="utf-8"><title>Daydream tileset</title>'
            '<style>body{background:#20232b;color:white;font:16px system-ui}img{image-rendering:pixelated;max-width:100%}</style>'
            '<h1>' + html.escape(source["name"]) + '</h1><p>Yellow outlines indicate full-tile collisions. '
            f'Boundary mismatches: {report["mismatch_count"]}. Human art review is still required.</p>'
            '<h2>Tiles (indices match source order)</h2><img src="preview.png"><h2>Example layout</h2><img src="layout.png">').encode()
    if "collisions.png" not in artifact_names(source):
        return legacy  # Keep already-approved legacy viewer bytes unchanged.
    details = [{"id": tile["id"], "polygons": collision.effective_polygons(tile)} for tile in source["tiles"]]
    return (legacy.replace(b'Yellow outlines indicate full-tile collisions.',
                           b'Yellow outlines indicate solid geometry; cyan indicates one-way geometry (local upward blocking).')
            + b'<h2>Collision coverage (not artwork)</h2><img src="collisions.png"><p>Raster overlays are approximate at tile-pixel resolution. Exact half-pixel coordinates and margins are listed below; shapes are not inferred from artwork alpha.</p><details><summary>Exact collision geometry</summary><pre>'
            + html.escape(json.dumps(details, indent=2)).encode() + b'</pre></details>')


def make_revision(source, provenance):
    source = validate_source(source)
    report = seams(source)
    files = {"source.json": sprite.encoded(source), "seams.json": sprite.encoded(report), "preview.html": viewer(source, report)}
    files.update({name: sprite.png_bytes(image) for name, image in images(source).items()})
    _, version = sprite.pillow()
    files["manifest.json"] = sprite.encoded({"schema_version": 1, "kind": KIND, "name": source["name"],
                                             "files": {name: sprite.digest(data) for name, data in files.items()},
                                             "generator": {"tool": "daydream-tilesets", "pillow": version}, "provenance": provenance})
    files[".gdignore"] = b""
    if sum(map(len, files.values())) > 24 * 1024 * 1024:
        raise ValueError("Tileset revision exceeds 24 MiB")
    return files


def load_revision(path):
    path = Path(path).expanduser().absolute()
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        source_data = sprite.read_regular("source.json", 1024 * 1024, dir_fd=fd, base=path)
        source = validate_source(json.loads(source_data))
        names = artifact_names(source)
        files = {name: sprite.read_regular(name, 8 * 1024 * 1024, dir_fd=fd, base=path) for name in sorted(names | {"manifest.json", ".gdignore"})}
    finally:
        os.close(fd)
    if sum(map(len, files.values())) > 24 * 1024 * 1024:
        raise ValueError("Tileset revision exceeds 24 MiB")
    if files["source.json"] != source_data:
        raise ValueError("Tileset source changed while reading the revision")
    manifest = json.loads(files["manifest.json"])
    if not isinstance(manifest, dict) or type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1 or manifest.get("kind") != KIND or manifest.get("name") != source["name"] or not isinstance(manifest.get("files"), dict) or set(manifest["files"]) != names:
        raise ValueError("Invalid tileset manifest")
    provenance, generator = manifest.get("provenance"), manifest.get("generator")
    if not isinstance(provenance, dict) or provenance.get("method") not in {"tileset-source", "tileset-transitions", "tileset-edit"} or not (provenance.get("license") is None or isinstance(provenance["license"], str)) or not isinstance(generator, dict) or generator.get("tool") != "daydream-tilesets" or not isinstance(generator.get("pillow"), str):
        raise ValueError("Invalid tileset provenance")
    if any(sprite.digest(files[name]) != manifest["files"][name] for name in names):
        raise ValueError("Tileset artifact hash mismatch")
    report = seams(source)
    if files["seams.json"] != sprite.encoded(report) or files["preview.html"] != viewer(source, report):
        raise ValueError("Tileset seam report/viewer does not match source")
    for name, expected in images(source).items():
        with sprite.open_image(files[name]) as actual:
            if actual.format != "PNG" or getattr(actual, "n_frames", 1) != 1 or actual.size != expected.size or actual.convert("RGBA").tobytes() != expected.tobytes():
                raise ValueError("Tileset image does not match editable source")
    return {"path": path, "source": source, "manifest": manifest, "files": files, "revision_hash": sprite.digest(files["manifest.json"])}
