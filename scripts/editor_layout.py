"""Serialize reviewed tile cells with Godot in an isolated, generated project.

No user project is opened, no TileMapLayer binary layout is authored here, and
the resulting scene has no script or editor-time hook.
"""

import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import tempfile
import time

from sprite_core import encoded, read_regular
from tileset_godot import outputs as runtime_outputs
import asset_access


SERIALIZER = '''extends SceneTree
func fail(message):
    push_error(message)
    quit(1)
func _initialize():
    call_deferred("serialize")
func serialize():
    var input = JSON.parse_string(FileAccess.get_file_as_string("res://_daydream_input.json"))
    if input.get("verify_only", false):
        verify(input)
        return
    var tiles = load(input.tileset) as TileSet
    if tiles == null:
        fail("Generated TileSet could not be loaded")
        return
    var layer = TileMapLayer.new()
    layer.name = input.name
    layer.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
    layer.tile_set = tiles
    layer.set_meta("daydream_revision_hash", input.revision_hash)
    layer.set_meta("daydream_layout_mode", "editor")
    layer.set_meta("daydream_serializer_version", input.engine_version)
    for cell in input.cells:
        layer.set_cell(Vector2i(cell.x, cell.y), 0, Vector2i(cell.atlas_x, cell.atlas_y))
    var packed = PackedScene.new()
    if packed.pack(layer) != OK:
        fail("Could not pack the generated tile layer")
        return
    if ResourceSaver.save(packed, input.scene, ResourceSaver.FLAG_OMIT_EDITOR_PROPERTIES) != OK:
        fail("Could not save the generated tile layer")
        return
    verify(input)
    layer.free()
func verify(input):
    var saved = ResourceLoader.load(input.scene, "PackedScene", ResourceLoader.CACHE_MODE_IGNORE) as PackedScene
    if saved == null:
        fail("Saved tile layer could not be reloaded")
        return
    var restored = saved.instantiate() as TileMapLayer
    if restored == null or restored.get_script() != null or restored.get_used_cells().size() != input.cells.size():
        fail("Saved tile layer did not preserve script-free cells before entering the tree")
        return
    for cell in input.cells:
        var position = Vector2i(cell.x, cell.y)
        if restored.get_cell_source_id(position) != 0 or restored.get_cell_atlas_coords(position) != Vector2i(cell.atlas_x, cell.atlas_y):
            fail("Saved tile identifiers differ from the reviewed layout")
            return
    var report = FileAccess.open("res://_daydream_result.json", FileAccess.WRITE)
    report.store_string(JSON.stringify({"cells": restored.get_used_cells().size(), "script_attached": false}))
    report.close()
    restored.free()
    quit()
'''


def executable(value):
    if not isinstance(value, str) or not value or not Path(value).is_absolute() or any(ord(ch) < 32 for ch in value):
        raise ValueError("Select an absolute Godot executable path, not flags or a shell command")
    return str(Path(value).resolve(strict=True))


def run_engine(binary, arguments, project, env, timeout, limit=1024 * 1024):
    """Bound output/time and terminate only the owned process group on failure."""
    process = subprocess.Popen([binary, *arguments], cwd=project, env=env, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)
    result = bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            end = time.monotonic() + timeout
            while selector.get_map():
                if time.monotonic() >= end:
                    raise ValueError("Godot serialization timed out; no existing game was run")
                for key, _ in selector.select(min(.1, max(0, end-time.monotonic()))):
                    chunk = os.read(key.fd, 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    result.extend(chunk)
                    if len(result) > limit:
                        raise ValueError("Godot serialization diagnostics exceeded their output limit")
            code = process.wait(timeout=max(.1, end-time.monotonic()))
        text = result.decode("utf-8", errors="replace")
        if code or re.search(r"^\s*(?:SCRIPT ERROR|USER ERROR|ERROR|Parse Error):", text, re.MULTILINE):
            raise ValueError("Godot serialization failed: " + text[-4000:])
        return text
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Godot serialization timed out; no target game was run") from exc
    finally:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            if process.poll() is None:
                process.wait(timeout=.25)
        except subprocess.TimeoutExpired:
            pass
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()
        process.stdout.close()


def stable_identifiers(scene, name, resource):
    """Normalize documented, scene-local labels only, never tile-map bytes.

    Only freshly generated one-node scenes enter this function. A second Godot
    process verifies the complete persisted cells after this normalization.
    """
    text = scene.decode("utf-8")
    external = re.findall(r'^\[ext_resource type="TileSet"(?: uid="uid://[a-z0-9]+")? path=("(?:[^"\\]|\\.)*") id="([A-Za-z0-9_]+)"\]$', text, re.MULTILINE)
    nodes = re.findall(r'^\[node name=("(?:[^"\\]|\\.)*") type="TileMapLayer"(?: unique_id=\d+)?\]$', text, re.MULTILINE)
    if len(external) != 1 or len(nodes) != 1 or len(re.findall(r'^\[node ', text, re.MULTILINE)) != 1 or len(re.findall(r'^\[ext_resource ', text, re.MULTILINE)) != 1 or re.search(r'^\[(?:sub_resource|connection) ', text, re.MULTILINE) or json.loads(external[0][0]) != "res://" + resource or json.loads(nodes[0]) != name:
        raise ValueError("Godot produced an unsupported scene structure; no target files were written")
    old_id = external[0][1]
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith('[gd_scene '):
            lines[index] = re.sub(r' uid="uid://[a-z0-9]+"', '', line)
        elif line.startswith('[ext_resource '):
            lines[index] = '[ext_resource type="TileSet" path=' + external[0][0] + ' id="Tileset"]'
        elif line.startswith('[node '):
            lines[index] = re.sub(r' unique_id=\d+', ' unique_id=1', line)
        else:
            lines[index] = line.replace('ExtResource(' + json.dumps(old_id) + ')', 'ExtResource("Tileset")')
    return ('\n'.join(lines) + '\n').encode()


def outputs(revision, asset_dir, source_dir, name, *, godot, godot_version=None, timeout=20, engine_info=None):
    """Build editor-visible output bytes; only the caller writes the target project."""
    binary = executable(godot)
    from engine_selection import version_pin
    version_pin(godot_version)
    if type(timeout) is not int or not 1 <= timeout <= 30:
        raise ValueError("Serialization timeout must be 1–30 seconds per process")
    files, paths, reserved = runtime_outputs(revision, asset_dir, source_dir, name)
    files.pop(paths["layout"])
    reserved.remove(paths.pop("layout") + ".uid")
    # No target-game files/scripts/settings are copied. All input is generated
    # from the already-validated revision and shared resource builder.
    with tempfile.TemporaryDirectory(prefix="daydream-editor-layout-") as temporary:
        base = Path(temporary)
        project = base / "project"; project.mkdir()
        env = {**os.environ, "HOME": str(base / "home"), "XDG_CONFIG_HOME": str(base / "config"),
               "XDG_DATA_HOME": str(base / "data"), "XDG_CACHE_HOME": str(base / "cache")}
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME"):
            Path(env[key]).mkdir()
        (project / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Daydream isolated serializer"\n')
        version = run_engine(binary, ["--version"], project, env, timeout, 8192).strip()
        match = re.match(r'^4\.(\d+)\.\d+(?:\.|$)', version)
        if not match or int(match[1]) < 3:
            raise ValueError("The detected editor must be Godot 4.3 or newer; no target project was changed")
        if godot_version is not None and not (version == godot_version or version.startswith(godot_version + '.')):
            raise ValueError(f"Godot version mismatch: expected {godot_version}, found {version}. Configure the matching editor once in .daydream/preview.json (advanced setup); Daydream will not upgrade the project or switch engines silently")
        for relative, data in files.items():
            if relative == paths["scene"]:
                continue
            target = project / relative
            if project not in target.resolve().parents:
                raise ValueError("Generated resource escaped the isolated serializer")
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("xb") as stream: stream.write(data)
        scene_path = project / paths["scene"]
        scene_path.parent.mkdir(parents=True, exist_ok=True)
        tiles = revision["source"]["tiles"]
        ids = {tile["id"]: index for index, tile in enumerate(tiles)}
        columns = min(8, len(tiles))
        cells = [{"x": cell["x"], "y": cell["y"], "atlas_x": ids[cell["tile"]] % columns,
                  "atlas_y": ids[cell["tile"]] // columns} for cell in revision["source"]["cells"]]
        (project / "_daydream_input.json").write_bytes(encoded({"name": name, "tileset": "res://" + paths["tileset"],
                "scene": "res://" + paths["scene"], "cells": cells, "revision_hash": revision["revision_hash"], "engine_version": version}))
        (project / "_daydream_serialize.gd").write_text(SERIALIZER)
        run_engine(binary, ["--headless", "--path", str(project), "--editor", "--import"], project, env, timeout)
        run_engine(binary, ["--headless", "--path", str(project), "--script", "res://_daydream_serialize.gd"], project, env, timeout)
        report_path = project / "_daydream_result.json"
        # These exact files were just generated in our owned scratch fixture;
        # they are not extra read authority over any user-project paths.
        with asset_access.grants({str(scene_path), str(report_path)}, set()):
            scene = stable_identifiers(read_regular(scene_path, 4 * 1024 * 1024), name, paths["tileset"])
        scene_path.write_bytes(scene)
        data_path = project / "_daydream_input.json"
        data = json.loads(data_path.read_bytes()); data["verify_only"] = True
        data_path.write_bytes(encoded(data))
        run_engine(binary, ["--headless", "--path", str(project), "--script", "res://_daydream_serialize.gd"], project, env, timeout)
        with asset_access.grants({str(scene_path), str(report_path)}, set()):
            report = json.loads(read_regular(report_path, 8192))
            persisted = read_regular(scene_path, 4 * 1024 * 1024)
        if report != {"cells": len(cells), "script_attached": False}:
            raise ValueError("Godot did not verify the script-free serialized cells")
        if persisted != scene or any(name in scene for name in (b'_daydream_input.json', b'_daydream_serialize.gd', b'_daydream_result.json')) or str(base).encode() in scene:
            raise ValueError("Generated scene leaked serializer-only paths")
        files[paths["scene"]] = scene
        if engine_info is not None:
            engine_info.update({"godot": binary, "version": version, "layout_mode": "editor",
                                "cells": len(cells), "script_attached": False, "game_project_executed": False})
    return files, paths, reserved
