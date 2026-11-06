"""Godot 4.3+ TileSet atlas, corner terrains, collisions and reusable map layer."""

import json
from collision_core import effective_polygons


def outputs(revision, asset_dir, source_dir, name):
    source = revision["source"]
    texture = f"{asset_dir}/{name}.png"
    resource = f"{asset_dir}/{name}.tileset.tres"
    scene = f"{asset_dir}/{name}.tscn"
    layout = f"{asset_dir}/{name}.layout.gd"
    editable = f"{source_dir}/{name}.json"
    tiles = source["tiles"]
    w, h = tiles[0]["source"]["width"], tiles[0]["source"]["height"]
    columns = min(8, len(tiles))
    text = ['[gd_resource type="TileSet" load_steps=3 format=3]\n\n',
            f'[ext_resource type="Texture2D" path={json.dumps("res://" + texture)} id="1"]\n\n',
            '[sub_resource type="TileSetAtlasSource" id="Atlas"]\ntexture = ExtResource("1")\n',
            f'texture_region_size = Vector2i({w}, {h})\n']
    corners = ("top_left_corner", "top_right_corner", "bottom_right_corner", "bottom_left_corner")
    for index, tile in enumerate(tiles):
        key = f"{index % columns}:{index // columns}/0"
        text += [f"{key} = 0\n", f"{key}/terrain_set = 0\n", f"{key}/terrain = {tile['terrain']}\n"]
        text += [f"{key}/terrains_peering_bit/{corner} = {terrain}\n" for corner, terrain in zip(corners, tile["corners"])]
        for polygon_index, polygon in enumerate(effective_polygons(tile)):
            points = [coordinate for px, py in polygon["points"] for coordinate in (px-w/2, py-h/2)]
            prefix = f"{key}/physics_layer_0/polygon_{polygon_index}"
            text += [f"{prefix}/points = PackedVector2Array({', '.join(map(str, points))})\n"]
            if "collisions" in tile:
                text += [f"{prefix}/one_way = {str(polygon['one_way']).lower()}\n", f"{prefix}/one_way_margin = {polygon['one_way_margin']}\n"]
    text += [f'\n[resource]\ntile_size = Vector2i({w}, {h})\n',
             f"physics_layer_0/collision_layer = {source['collision_layer']}\nphysics_layer_0/collision_mask = {source['collision_mask']}\n",
             "terrain_set_0/mode = 1\n"]
    for index, terrain in enumerate(source["terrains"]):
        text += [f"terrain_set_0/terrain_{index}/name = {json.dumps(terrain)}\n",
                 f"terrain_set_0/terrain_{index}/color = Color({(index % 3 + 1)/4}, {(index % 2 + 1)/3}, 0.5, 1)\n"]
    text.append('sources/0 = SubResource("Atlas")\n')
    ids = {tile["id"]: index for index, tile in enumerate(tiles)}
    # Documented set_cell() calls avoid writing undocumented version-specific
    # TileMapLayer binary serialization. No @tool or editor-time execution.
    script = "extends TileMapLayer\n\n# Reviewed layout, populated at runtime only.\nfunc _ready() -> void:\n"
    if not source["cells"]:
        script += "\tpass\n"
    for cell in source["cells"]:
        index = ids[cell["tile"]]
        script += f"\tset_cell(Vector2i({cell['x']}, {cell['y']}), 0, Vector2i({index % columns}, {index // columns}))\n"
    scene_text = (f'[gd_scene load_steps=3 format=3]\n\n[ext_resource type="TileSet" path={json.dumps("res://" + resource)} id="1"]\n'
                  f'[ext_resource type="Script" path={json.dumps("res://" + layout)} id="2"]\n\n'
                  f'[node name={json.dumps(name)} type="TileMapLayer"]\ntexture_filter = 1\ntile_set = ExtResource("1")\nscript = ExtResource("2")\n')
    return ({texture: revision["files"]["atlas.png"], resource: "".join(text).encode(), scene: scene_text.encode(),
             layout: script.encode(), editable: revision["files"]["source.json"]},
            {"texture": texture, "tileset": resource, "scene": scene, "layout": layout, "source": editable},
            [texture + ".import", resource + ".uid", scene + ".uid", layout + ".uid"])
