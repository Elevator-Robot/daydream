"""Synthetic review fixtures; never reads or changes an existing game."""

import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from operations import execute


def create(root):
    root = Path(root)
    (root / "project.godot").write_text('config_version=5\n[application]\nconfig/name="Synthetic review fixture"\n')
    def call(op, data):
        result = execute(op, data, root)
        if not result["ok"]: raise ValueError(result)
    call("project.init", {"apply": True})
    seed = {"schema_version": 1, "name": "dot", "width": 4, "height": 4, "palette": {"a": "#ffffff", "b": "#334455"}, "pixels": ["aaaa"] * 4}
    call("sprite.create", {"source": seed, "output": "art/dot", "apply": True})
    call("animation.assemble", {"name": "walk", "pivot": [2, 4], "frames": [{"id": "a", "bundle": "art/dot"}],
                                "animations": [{"name": "idle", "fps": 4, "loop": True, "frames": [{"frame": "a", "duration": 1}]}],
                                "default_animation": "idle", "output": "art/walk", "apply": True})
    tiles = {"schema_version": 1, "name": "floor", "terrains": ["floor"],
             "tiles": [{"id": "floor", "source": seed, "terrain": 0, "corners": [0, 0, 0, 0], "solid": False}],
             "cells": [{"x": 0, "y": 0, "tile": "floor"}], "collision_layer": 1, "collision_mask": 1}
    call("tileset.create", {"source": tiles, "output": "art/floor", "apply": True})
    return {"sprite": "art/dot", "animation": "art/walk", "tileset": "art/floor"}


if __name__ == "__main__":
    print(json.dumps(create(sys.argv[1])))
