"""Create SpriteFrames/AnimatedSprite2D resources without launching Godot."""

import json


def outputs(revision, asset_dir, source_dir, name):
    source = revision["source"]
    texture = asset_dir + "/" + name + ".png"
    resource = asset_dir + "/" + name + ".frames.tres"
    scene = asset_dir + "/" + name + ".tscn"
    editable = source_dir + "/" + name + ".json"
    count = len(source["frames"])
    columns = min(8, count)
    ids = {frame["id"]: index for index, frame in enumerate(source["frames"])}
    chunks = [f'[gd_resource type="SpriteFrames" load_steps={count + 2} format=3]\n\n',
              '[ext_resource type="Texture2D" path=' + json.dumps("res://" + texture, ensure_ascii=False) + ' id="1"]\n\n']
    for index in range(count):
        x, y = index % columns * source["width"], index // columns * source["height"]
        chunks.append(f'[sub_resource type="AtlasTexture" id="AtlasTexture_{index}"]\natlas = ExtResource("1")\nregion = Rect2({x}, {y}, {source["width"]}, {source["height"]})\n\n')
    clips = []
    for animation in source["animations"]:
        frames = [f'{{"duration": {json.dumps(step["duration"])}, "texture": SubResource("AtlasTexture_{ids[step["frame"]]}")}}' for step in animation["frames"]]
        # loop is the original Godot 4 resource key; loop_mode is the equivalent
        # current key. Both encode the same linear/no-loop behavior.
        clips.append('{"frames": [' + ", ".join(frames) + '], "loop": ' + str(animation["loop"]).lower()
                     + ', "loop_mode": ' + ("1" if animation["loop"] else "0") + ', "name": &'
                     + json.dumps(animation["name"]) + ', "speed": ' + json.dumps(animation["fps"]) + '}')
    chunks.append('[resource]\nanimations = [' + ",\n".join(clips) + ']\n')
    pivot_x, pivot_y = source["pivot"]
    default = json.dumps(source["default_animation"])
    scene_text = ('[gd_scene load_steps=2 format=3]\n\n[ext_resource type="SpriteFrames" path='
                  + json.dumps("res://" + resource, ensure_ascii=False) + ' id="1"]\n\n[node name='
                  + json.dumps(name) + ' type="AnimatedSprite2D"]\ntexture_filter = 1\nsprite_frames = ExtResource("1")\n'
                  + f'animation = &{default}\nautoplay = {default}\ncentered = false\noffset = Vector2({-pivot_x}, {-pivot_y})\n')
    return ({texture: revision["files"]["spritesheet.png"], resource: "".join(chunks).encode("utf-8"),
             scene: scene_text.encode("utf-8"), editable: revision["files"]["source.json"]},
            {"texture": texture, "frames": resource, "scene": scene, "source": editable},
            [texture + ".import", resource + ".uid", scene + ".uid"])
