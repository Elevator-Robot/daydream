"""The one authored operation catalog: schemas, handlers, authority, discovery."""

import copy
from dataclasses import dataclass
import math
import re

import operation_handlers as handlers
import dashboard


def obj(properties, required):
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


PATH = {"type": "string", "minLength": 1, "maxLength": 4096, "description": "Project-relative path, or absolute inside the active project. No traversal or symlink components."}
SLUG = {"type": "string", "pattern": "^[a-z][a-z0-9_-]{0,47}$", "maxLength": 48}
SYMBOL = {"type": "string", "pattern": "^[A-Za-z0-9.]$", "minLength": 1, "maxLength": 1}
COLOR = {"type": "string", "pattern": "^#[0-9a-fA-F]{6}$", "minLength": 7, "maxLength": 7}
VERSION = {"type": "integer", "enum": [1]}
APPLY = {"type": "boolean", "default": False, "description": "False previews without writes. True requests the approved/authorized write; never implies artwork approval."}
PIXELS = {"type": "array", "minItems": 1, "maxItems": 256, "items": {"type": "string", "minLength": 1, "maxLength": 256, "pattern": "^[A-Za-z0-9.]+$"}}
SPRITE = obj({"schema_version": VERSION, "name": SLUG, "width": {"type": "integer", "minimum": 1, "maximum": 256},
              "height": {"type": "integer", "minimum": 1, "maximum": 256},
              "palette": {"type": "object", "minProperties": 1, "maxProperties": 32,
                          "propertyNames": {"type": "string", "pattern": "^[A-Za-z0-9]$", "maxLength": 1}, "additionalProperties": COLOR},
              "pixels": PIXELS}, ["schema_version", "name", "width", "height", "palette", "pixels"])
PATCH_STEP = {"oneOf": [
    obj({"op": {"enum": ["recolor"]}, "symbol": SYMBOL, "color": COLOR}, ["op", "symbol", "color"]),
    obj({"op": {"enum": ["mirror"]}, "axis": {"enum": ["horizontal", "vertical"]}}, ["op", "axis"]),
    obj({"op": {"enum": ["paint"]}, "x": {"type": "integer", "minimum": 0, "maximum": 255},
         "y": {"type": "integer", "minimum": 0, "maximum": 255}, "symbol": SYMBOL}, ["op", "x", "y", "symbol"]),
    obj({"op": {"enum": ["rect"]}, "box": {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "integer", "minimum": 0, "maximum": 255}}, "symbol": SYMBOL}, ["op", "box", "symbol"]),
]}
PATCH = obj({"schema_version": VERSION, "operations": {"type": "array", "minItems": 1, "maxItems": 1024, "items": PATCH_STEP}}, ["schema_version", "operations"])
PIVOT = {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer", "minimum": 0, "maximum": 128}}
STEP = obj({"frame": SLUG, "duration": {"type": "number", "exclusiveMinimum": 0, "maximum": 150}}, ["frame", "duration"])
CLIP = obj({"name": SLUG, "fps": {"type": "number", "minimum": 1, "maximum": 30}, "loop": {"type": "boolean"},
            "frames": {"type": "array", "minItems": 1, "items": STEP}}, ["name", "fps", "loop", "frames"])
CLIPS = {"type": "array", "minItems": 1, "maxItems": 8, "items": CLIP}
RECIPE_FRAME = {"oneOf": [obj({"id": SLUG}, ["id"]), obj({"id": SLUG, "patch": PATCH}, ["id", "patch"]), obj({"id": SLUG, "pixels": PIXELS}, ["id", "pixels"])]}
RECIPE = obj({"schema_version": VERSION, "name": SLUG, "pivot": PIVOT,
              "frames": {"type": "array", "minItems": 1, "items": RECIPE_FRAME},
              "animations": CLIPS, "default_animation": SLUG}, ["schema_version", "name", "pivot", "frames", "animations", "default_animation"])
ANIMATION_PATCH = obj({"schema_version": VERSION, "operations": {"type": "array", "minItems": 1, "maxItems": 128, "items": {"oneOf": [
    obj({"op": {"enum": ["frame"]}, "id": SLUG, "patch": PATCH}, ["op", "id", "patch"]),
    PATCH_STEP["oneOf"][0],
    obj({"op": {"enum": ["animation"]}, "value": CLIP}, ["op", "value"]),
    obj({"op": {"enum": ["pivot"]}, "value": PIVOT}, ["op", "value"]),
    obj({"op": {"enum": ["default"]}, "animation": SLUG}, ["op", "animation"]),
]}}}, ["schema_version", "operations"])
TERRAIN_ID = {"type": "integer", "minimum": 0, "maximum": 7}
CORNERS = {"type": "array", "minItems": 4, "maxItems": 4, "items": {"type": "integer", "minimum": -1, "maximum": 7}, "description": "Terrain indices (-1 is empty): top-left, top-right, bottom-right, bottom-left; Godot match-corners mode."}
CELLS = {"type": "array", "maxItems": 1024, "items": obj({"x": {"type": "integer", "minimum": 0, "maximum": 63}, "y": {"type": "integer", "minimum": 0, "maximum": 63}, "tile": SLUG}, ["x", "y", "tile"])}
BITMASK = {"type": "integer", "minimum": 0, "maximum": 4294967295}
COLLISIONS = {"type": "array", "maxItems": 8, "description": "Explicit convex polygons; use solid:false. Tile-local pixels from top-left, half-pixel grid. Empty array disables collisions.", "items": obj({
    "points": {"type": "array", "minItems": 3, "maxItems": 16, "items": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "number", "minimum": 0, "maximum": 64}}},
    "one_way": {"type": "boolean", "default": False},
    "one_way_margin": {"type": "number", "minimum": 0, "maximum": 16, "default": 1},
}, ["points"])}
COLLISION_PRESET = obj({"preset": {"type": "string", "enum": ["none", "full", "slope_up_right", "slope_up_left", "platform"]},
                        "one_way": {"type": "boolean", "description": "Defaults true for platform, false otherwise."},
                        "one_way_margin": {"type": "number", "minimum": 0, "maximum": 16},
                        "thickness": {"type": "number", "minimum": .5, "maximum": 64, "description": "Platform only; half-pixel grid, bounded by tile height. Default 1 pixel."}}, ["preset"])
TILESET_SOURCE = obj({"schema_version": VERSION, "name": SLUG,
                      "terrains": {"type": "array", "minItems": 1, "maxItems": 8, "items": SLUG},
                      "tiles": {"type": "array", "minItems": 1, "maxItems": 192, "items": obj({"id": SLUG, "source": SPRITE, "terrain": TERRAIN_ID, "corners": CORNERS, "solid": {"type": "boolean"}, "collisions": COLLISIONS}, ["id", "source", "terrain", "corners", "solid"])},
                      "cells": CELLS, "collision_layer": BITMASK, "collision_mask": BITMASK},
                     ["schema_version", "name", "terrains", "tiles", "cells", "collision_layer", "collision_mask"])


@dataclass(frozen=True)
class Operation:
    name: str
    summary: str
    schema: dict
    handler: object
    effect: str = "write"
    native: bool = True
    direct: bool = True
    paths: tuple = ()  # (input field, file/static_bundle/animation_bundle/output)
    project_reads: tuple = ()
    engine: bool = False
    discovery: bool = False

    def metadata(self):
        return {"name": self.name, "summary": self.summary, "input": copy.deepcopy(self.schema), "effect": self.effect,
                "native": self.native, "tool": "daydream_" + self.name.replace(".", "_") if self.native and self.direct else None,
                "paths": [list(item) for item in self.paths], "project_reads": list(self.project_reads),
                "preview_default": self.effect != "read", "engine_serialization": self.engine}


HASH = {"type": "string", "pattern": "^[0-9a-f]{64}$", "maxLength": 64}
LABEL = {"type": "string", "minLength": 1, "maxLength": 120, "description": "Friendly display name, e.g. Potion Shop Floor. File-safe IDs are derived automatically."}
IMPORT = obj({"bundle": PATH, "name": LABEL, "destination": PATH, "revision_hash": HASH, "plan_hash": HASH, "apply": APPLY,
              "strategy": {"type": "string", "enum": ["new", "copy", "update"], "default": "new", "description": "copy automatically chooses unused filenames; update keeps a selected managed asset's paths, protects manual edits and archives old bytes. Updates require a reviewed plan_hash on apply; get explicit user update authorization first."},
              "target": SLUG}, ["bundle"])
APPROVE = obj({"bundle": PATH, "revision_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$", "maxLength": 64},
               "reviewer": {"type": "string", "minLength": 1, "maxLength": 120}, "apply": APPLY}, ["bundle", "revision_hash", "reviewer"])
PROJECT_READS = ("project.godot", ".daydream/config.json", ".daydream/assets.json")
EDITOR_IMPORT = obj({**IMPORT["properties"],
                     "godot": {"type": "string", "minLength": 1, "maxLength": 4096, "pattern": "^/", "description": "Advanced optional override. Normally auto-detected from project settings, GODOT_BIN or PATH; execution permission is still required."},
                     "godot_version": {"type": "string", "minLength": 3, "maxLength": 128, "pattern": "^4\\.[0-9]+(?:\\.[0-9]+(?:\\.[A-Za-z0-9_.-]+)?)?$", "description": "Advanced optional expected version. Normally read from project settings/features; no project upgrade is performed."},
                     "engine_timeout": {"type": "integer", "minimum": 1, "maximum": 30, "default": 20}}, ["bundle"])
OPERATIONS = (
    Operation("project.init", "Preview or initialize non-overwriting Daydream project metadata", obj({"assets_dir": PATH, "sources_dir": PATH, "apply": APPLY}, []), handlers.project_init, direct=False, project_reads=PROJECT_READS + (".daydream/.gitignore", ".daydream/.gdignore")),
    Operation("sprite.create", "Create a transparent static pixel-art sprite and nearest-neighbor preview", obj({"source": SPRITE, "output": PATH, "apply": APPLY}, ["source", "output"]), handlers.sprite_create, paths=(("output", "output"),)),
    Operation("sprite.from_png", "Convert an existing bounded PNG into an editable sprite revision", obj({"image": PATH, "name": SLUG, "output": PATH, "apply": APPLY}, ["image", "name", "output"]), handlers.sprite_from_png, direct=False, paths=(("image", "file"), ("output", "output"))),
    Operation("sprite.edit", "Recolor, mirror, paint or fill a rectangle in a fresh sprite revision", obj({"bundle": PATH, "patch": PATCH, "output": PATH, "apply": APPLY}, ["bundle", "patch", "output"]), handlers.sprite_edit, paths=(("bundle", "static_bundle"), ("output", "output"))),
    Operation("sprite.inspect", "Validate a static sprite revision and return its exact hash and image preview", obj({"bundle": PATH}, ["bundle"]), handlers.sprite_inspect, effect="read", paths=(("bundle", "static_bundle"),)),
    Operation("sprite.approve", "User review UI or explicitly authorized CLI only: approve one exact static sprite", APPROVE, handlers.sprite_approve, effect="approval", native=False, direct=False, paths=(("bundle", "static_bundle"),)),
    Operation("sprite.import", "Preview or import an approved static sprite into Godot without overwrites", IMPORT, handlers.sprite_import, paths=(("bundle", "static_bundle"),), project_reads=PROJECT_READS),
    Operation("animation.create", "Create named animation clips, atlas, motion previews and contact sheets from a static base", obj({"recipe": RECIPE, "base": PATH, "output": PATH, "apply": APPLY}, ["recipe", "base", "output"]), handlers.animation_create, paths=(("base", "static_bundle"), ("output", "output"))),
    Operation("animation.assemble", "Assemble existing sprite frame revisions into named animations without an arbitrary frame-count cap; source, image and memory safety budgets apply", obj({"name": SLUG, "pivot": PIVOT, "frames": {"type": "array", "minItems": 1, "items": obj({"id": SLUG, "bundle": PATH}, ["id", "bundle"])}, "animations": CLIPS, "default_animation": SLUG, "output": PATH, "apply": APPLY}, ["name", "pivot", "frames", "animations", "default_animation", "output"]), handlers.animation_assemble, paths=(("frames.*.bundle", "static_bundle"), ("output", "output"))),
    Operation("animation.edit", "Revise frames, global palette, timing, loop or pivot without changing the original animation", obj({"bundle": PATH, "patch": ANIMATION_PATCH, "output": PATH, "apply": APPLY}, ["bundle", "patch", "output"]), handlers.animation_edit, paths=(("bundle", "animation_bundle"), ("output", "output"))),
    Operation("animation.inspect", "Validate animation artifacts and return frame/timing data and motion/contact preview paths", obj({"bundle": PATH}, ["bundle"]), handlers.animation_inspect, effect="read", paths=(("bundle", "animation_bundle"),)),
    Operation("animation.approve", "User review UI or explicitly authorized CLI only: approve an entire exact animation", APPROVE, handlers.animation_approve, effect="approval", native=False, direct=False, paths=(("bundle", "animation_bundle"),)),
    Operation("animation.import", "Preview or import an approved atlas, SpriteFrames and AnimatedSprite2D scene", IMPORT, handlers.animation_import, paths=(("bundle", "animation_bundle"),), project_reads=PROJECT_READS),
    Operation("tileset.create", "Create editable walls, floors and environment tiles with terrain corners, collision metadata, atlas and seam/layout previews", obj({"source": TILESET_SOURCE, "output": PATH, "apply": APPLY}, ["source", "output"]), handlers.tileset_create, paths=(("output", "output"),)),
    Operation("tileset.transitions", "Generate 162 matching center/corner terrain tiles from two seamless static sprite revisions, including floor/wall/empty boundaries and corners", obj({"background": PATH, "foreground": PATH, "name": SLUG, "terrains": {"type": "array", "minItems": 2, "maxItems": 2, "items": SLUG}, "solid_foreground": {"type": "boolean"}, "output": PATH, "apply": APPLY}, ["background", "foreground", "name", "terrains", "output"]), handlers.tileset_transitions, paths=(("background", "static_bundle"), ("foreground", "static_bundle"), ("output", "output"))),
    Operation("tileset.edit", "Revise tile pixels, convex collision polygons, slopes, one-way platforms, terrain and layout in a fresh unapproved revision. Choose only one of solid, collisions or collision_preset per tile.", obj({"bundle": PATH, "tiles": {"type": "array", "maxItems": 64, "items": obj({"id": SLUG, "patch": PATCH, "solid": {"type": "boolean"}, "collisions": COLLISIONS, "collision_preset": COLLISION_PRESET, "terrain": TERRAIN_ID, "corners": CORNERS}, ["id"])}, "cells": CELLS, "recolor": obj({"symbol": SYMBOL, "color": COLOR}, ["symbol", "color"]), "collision_layer": BITMASK, "collision_mask": BITMASK, "output": PATH, "apply": APPLY}, ["bundle", "tiles", "output"]), handlers.tileset_edit, paths=(("bundle", "tileset_bundle"), ("output", "output"))),
    Operation("tileset.inspect", "Validate an environment tileset and report compatible pixel edges, terrain coverage, collision flags and review artifact paths", obj({"bundle": PATH}, ["bundle"]), handlers.tileset_inspect, effect="read", paths=(("bundle", "tileset_bundle"),)),
    Operation("tileset.approve", "User review UI or explicitly authorized CLI only: approve exact tileset pixels, transitions, layout and collision metadata", APPROVE, handlers.tileset_approve, effect="approval", native=False, direct=False, paths=(("bundle", "tileset_bundle"),)),
    Operation("tileset.import", "Preview or import an approved seam-checked TileSet and TileMapLayer with full tiles, convex polygons, slopes and one-way collision settings for Godot 4.3+", IMPORT, handlers.tileset_import, paths=(("bundle", "tileset_bundle"),), project_reads=PROJECT_READS),
    Operation("tileset.editor_import", "Preview/apply a script-free editor-visible TileMapLayer using auto-detected Godot checked against project settings. Even preview needs engine permission and runs only an isolated generated fixture, never game code. Never overwrites an existing map.", EDITOR_IMPORT, handlers.tileset_editor_import, paths=(("bundle", "tileset_bundle"),), project_reads=PROJECT_READS + ('.daydream/preview.json',), engine=True),
    Operation("review.inspect", "Read exact-revision approval state and retained user feedback for a sprite, animation or tileset", obj({"bundle": PATH, "kind": {"type": "string", "enum": ["sprite", "animation", "tileset"]}}, ["bundle", "kind"]), handlers.review_inspect, effect="read", direct=False, paths=(("bundle", "review_bundle"),)),
    Operation("review.feedback", "User UI or explicitly authorized CLI only: add exact-revision change-request feedback while retaining earlier notes; identical submissions are kept once. Never approve the candidate.", obj({"bundle": PATH, "kind": {"type": "string", "enum": ["sprite", "animation", "tileset"]}, "revision_hash": HASH, "reviewer": {"type": "string", "minLength": 1, "maxLength": 120}, "feedback": {"type": "string", "minLength": 1, "maxLength": 4000}, "apply": APPLY}, ["bundle", "kind", "revision_hash", "reviewer", "feedback"]), handlers.review_feedback, native=False, direct=False, paths=(("bundle", "review_bundle"),)),
    Operation('assets.list', 'List current asset candidates and managed import status; optional history reveals older revisions. Does not approve or load Godot.', obj({'history': {'type': 'boolean', 'default': False}}, []), handlers.assets_list, effect='read', project_reads=PROJECT_READS, discovery=True),
    Operation('assets.options', 'Suggest add-copy or safe-update choices for one revision, including manual-edit protection and current scene path.', obj({'bundle': PATH, 'kind': {'type': 'string', 'enum': ['sprite', 'animation', 'tileset']}}, ['bundle', 'kind']), handlers.assets_options, effect='read', direct=False, paths=(('bundle', 'review_bundle'),), project_reads=PROJECT_READS, discovery=True),
    Operation('dashboard.catalog', 'Read the project artwork collection, latest/history identities and managed outputs. Includes existing project images; never imports or runs game code.', obj({}, []), dashboard.catalog, effect='read', direct=False, project_reads=PROJECT_READS, discovery=True),
    Operation('dashboard.inspect', 'Inspect sprite, animation, tileset or existing project-image details for the project dashboard. Read-only.', obj({'path': PATH, 'kind': {'enum': ['sprite', 'animation', 'tileset', 'image']}, 'revision_hash': HASH, 'resources': {'type': 'array', 'maxItems': 500, 'items': PATH}}, ['path', 'kind']), dashboard.inspect_asset, effect='read', direct=False, paths=(('path', 'dashboard_asset'), ('resources.*', 'file')), discovery=True),
    Operation('dashboard.media', 'Read a validated dashboard image as bounded PNG data. Browser transport; prefer dashboard.inspect for metadata.', obj({'path': PATH, 'kind': {'enum': ['sprite', 'animation', 'tileset', 'image']}, 'image': {'type': 'string', 'maxLength': 64}, 'revision_hash': HASH, 'resources': {'type': 'array', 'maxItems': 500, 'items': PATH}}, ['path', 'kind']), dashboard.media, effect='read', direct=False, paths=(('path', 'dashboard_asset'), ('resources.*', 'file')), discovery=True),
)

# Public workflow schemas allow ordinary display labels and automatically placed
# immutable revisions. The canonical rendering formats still use validated IDs.
for _op in OPERATIONS:
    if _op.name in {'sprite.create', 'sprite.from_png', 'sprite.edit', 'animation.create', 'animation.assemble', 'animation.edit', 'tileset.create', 'tileset.transitions', 'tileset.edit'}:
        _op.schema['required'] = [key for key in _op.schema['required'] if key != 'output']
        _op.schema['properties']['output'] = {**PATH, 'description': 'Optional advanced output directory. Omit for automatic hidden revision storage; no manual version naming needed.'}
        if _op.name in {'sprite.create', 'tileset.create', 'animation.create'}:
            _field = 'recipe' if _op.name == 'animation.create' else 'source'
            _schema = copy.deepcopy(_op.schema['properties'][_field])
            _schema['properties']['name'] = LABEL
            _op.schema['properties'][_field] = _schema
        elif 'name' in _op.schema['properties']:
            _op.schema['properties']['name'] = LABEL


def find(name):
    return next((operation for operation in OPERATIONS if operation.name == name), None)


def validate(schema, value, path="input", depth=0):
    if depth > 64:
        raise ValueError("Input nesting exceeds its limit")
    if "oneOf" in schema:
        matches = 0
        for candidate in schema["oneOf"]:
            try:
                validate(candidate, value, path, depth + 1)
                matches += 1
            except ValueError:
                pass
        if matches != 1:
            raise ValueError(f"{path} must match exactly one supported form")
        return
    kind = schema.get("type")
    matches = {"object": isinstance(value, dict), "array": isinstance(value, list), "string": isinstance(value, str),
               "boolean": type(value) is bool, "integer": type(value) is int,
               "number": type(value) in (int, float) and (type(value) is int or math.isfinite(value))}
    if kind is not None and not matches.get(kind, False):
        raise ValueError(f"{path} must be {kind}")
    if "enum" in schema and not any(type(value) is type(item) and value == item for item in schema["enum"]):
        raise ValueError(f"{path} is not a supported value")
    if kind in ("integer", "number"):
        for key, invalid in (("minimum", value < schema.get("minimum", value)), ("maximum", value > schema.get("maximum", value)), ("exclusiveMinimum", value <= schema.get("exclusiveMinimum", value - 1))):
            if key in schema and invalid: raise ValueError(f"{path} violates {key}")
    if kind == "string":
        if not schema.get("minLength", 0) <= len(value) <= schema.get("maxLength", len(value)) or ("pattern" in schema and re.search(schema["pattern"], value) is None):
            raise ValueError(f"{path} has an invalid length or format")
    if kind == "array":
        if not schema.get("minItems", 0) <= len(value) <= schema.get("maxItems", len(value)):
            raise ValueError(f"{path} has an invalid item count")
        for index, item in enumerate(value): validate(schema.get("items", {}), item, f"{path}[{index}]", depth + 1)
    if kind == "object":
        if not schema.get("minProperties", 0) <= len(value) <= schema.get("maxProperties", len(value)):
            raise ValueError(f"{path} has an invalid property count")
        if any(key not in value for key in schema.get("required", [])):
            raise ValueError(f"{path} is missing required fields: {', '.join(key for key in schema['required'] if key not in value)}")
        properties, additional = schema.get("properties", {}), schema.get("additionalProperties", True)
        for key, item in value.items():
            if not isinstance(key, str): raise ValueError(f"{path} keys must be strings")
            if "propertyNames" in schema: validate(schema["propertyNames"], key, path + ".key", depth + 1)
            if key in properties: validate(properties[key], item, f"{path}.{key}", depth + 1)
            elif additional is False: raise ValueError(f"{path} has an unknown field: {key}")
            elif isinstance(additional, dict): validate(additional, item, f"{path}.{key}", depth + 1)


def search(query="", limit=10):
    terms = set(re.findall(r"[a-z0-9]+", query.lower()))
    synonyms = {"sprites": "sprite", "frames": "animation", "animate": "animation", "walking": "animation", "png": "sprite", "walls": "tileset", "floors": "tileset", "tiles": "tileset", "terrain": "tileset", "tilesets": "tileset"}
    terms |= {synonyms[term] for term in terms if term in synonyms}
    ranked = []
    for operation in OPERATIONS:
        words = set(re.findall(r"[a-z0-9]+", operation.summary.lower()))
        score = sum(3 if term in operation.name else 1 if term in words else 0 for term in terms)
        if not terms or score:
            ranked.append((score + (100 if query.strip() == operation.name else 0), operation.name, operation))
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [operation.metadata() for _, _, operation in ranked[:limit]]
