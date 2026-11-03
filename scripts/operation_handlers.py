"""Shared asset operations. Adapters do not implement rendering or approval logic."""

import copy

import animation_core as animation
from animation_godot import outputs as animation_outputs
from init_project import init_project
import sprite_core as sprite
import sprite_store as store
import tileset_core as tileset
from tileset_godot import outputs as tileset_outputs


def project_init(context, data):
    plan = init_project(context.root, apply=data.get("apply", False), assets_dir=data.get("assets_dir", "assets"), sources_dir=data.get("sources_dir", "art"))
    writes = [context.path(item["path"]) for item in plan if item["action"] == "create"]
    return {"files": [{"path": item["path"], "action": item["action"]} for item in plan]}, writes


def sprite_create(context, data):
    source = sprite.validate_source(data["source"])
    files = sprite.make_revision(source, {"method": "pixel-spec", "input_sha256": sprite.digest(sprite.encoded(source)), "license": None})
    return save(context, data, files)


def sprite_from_png(context, data):
    source, provenance = sprite.source_from_png(context.path(data["image"]), data["name"])
    return save(context, data, sprite.make_revision(source, provenance))


def sprite_edit(context, data):
    parent = sprite.load_revision(context.path(data["bundle"]))
    source = sprite.edit_source(parent["source"], data["patch"])
    provenance = {"method": "edit", "parent_revision_hash": parent["revision_hash"], "patch_sha256": sprite.digest(sprite.encoded(data["patch"])), "license": parent["manifest"]["provenance"].get("license")}
    return save(context, data, sprite.make_revision(source, provenance))


def sprite_inspect(context, data):
    revision = sprite.load_revision(context.path(data["bundle"]))
    return {"name": revision["source"]["name"], "width": revision["source"]["width"], "height": revision["source"]["height"],
            "palette": revision["source"]["palette"], "revision_hash": revision["revision_hash"],
            "preview": str(revision["path"] / "preview.png"), "artifact_kind": "static_image"}, []


def sprite_approve(context, data):
    return approve(context, data, sprite.load_revision)


def sprite_import(context, data):
    return importing(context, data, sprite.load_revision, store.static_outputs)


def animation_create(context, data):
    base = sprite.load_revision(context.path(data["base"]))
    source = animation.source_from_recipe(base["source"], data["recipe"])
    provenance = {"method": "animation-recipe", "base_revision_hash": base["revision_hash"],
                  "recipe_sha256": sprite.digest(sprite.encoded(data["recipe"])), "license": base["manifest"]["provenance"].get("license")}
    return save(context, data, animation.make_revision(source, provenance), animation.KIND)


def animation_assemble(context, data):
    frames, parents, palettes = [], [], []
    for frame in data["frames"]:
        revision = sprite.load_revision(context.path(frame["bundle"]))
        frames.append({"id": frame["id"], "source": copy.deepcopy(revision["source"])})
        parents.append(revision["revision_hash"])
        palettes.append(revision["manifest"]["provenance"].get("license"))
    first = frames[0]["source"]
    source = animation.validate_source({"schema_version": 1, "name": data["name"], "width": first["width"], "height": first["height"],
                                       "pivot": data["pivot"], "frames": frames, "animations": data["animations"], "default_animation": data["default_animation"]})
    provenance = {"method": "animation-assemble", "parent_revision_hashes": parents, "license": palettes[0] if all(value == palettes[0] for value in palettes) else None}
    return save(context, data, animation.make_revision(source, provenance), animation.KIND)


def animation_edit(context, data):
    parent = animation.load_revision(context.path(data["bundle"]))
    source = animation.edit_animation(parent["source"], data["patch"])
    provenance = {"method": "animation-edit", "parent_revision_hash": parent["revision_hash"],
                  "patch_sha256": sprite.digest(sprite.encoded(data["patch"])), "license": parent["manifest"]["provenance"].get("license")}
    return save(context, data, animation.make_revision(source, provenance), animation.KIND)


def animation_inspect(context, data):
    revision = animation.load_revision(context.path(data["bundle"]))
    source = revision["source"]
    return {"name": source["name"], "width": source["width"], "height": source["height"], "pivot": source["pivot"],
            "frames": [frame["id"] for frame in source["frames"]], "animations": source["animations"],
            "revision_hash": revision["revision_hash"], "preview": str(revision["path"] / "preview.html"),
            "spritesheet": str(revision["path"] / "spritesheet.png"), "artifact_kind": "animation",
            "previews": [{"animation": clip["name"], "visual_frames": len(animation.motion_frames(source, clip)[0]),
                          "motion": str(revision["path"] / (clip["name"] + ".motion.png")),
                          "contact_sheet": str(revision["path"] / (clip["name"] + ".contact.png"))} for clip in source["animations"]]}, []


def animation_approve(context, data):
    return approve(context, data, animation.load_revision)


def animation_import(context, data):
    return importing(context, data, animation.load_revision, animation_outputs)


def tileset_create(context, data):
    source = tileset.validate_source(data["source"])
    return save(context, data, tileset.make_revision(source, {"method": "tileset-source", "input_sha256": sprite.digest(sprite.encoded(source)), "license": None}), tileset.KIND)


def tileset_transitions(context, data):
    background = sprite.load_revision(context.path(data["background"]))
    foreground = sprite.load_revision(context.path(data["foreground"]))
    source = tileset.transitions(background["source"], foreground["source"], data["name"], data["terrains"], data.get("solid_foreground", False))
    provenance = {"method": "tileset-transitions", "parent_revision_hashes": [background["revision_hash"], foreground["revision_hash"]],
                  "license": background["manifest"]["provenance"].get("license") if background["manifest"]["provenance"].get("license") == foreground["manifest"]["provenance"].get("license") else None}
    return save(context, data, tileset.make_revision(source, provenance), tileset.KIND)


def tileset_edit(context, data):
    parent = tileset.load_revision(context.path(data["bundle"]))
    source = copy.deepcopy(parent["source"])
    by_id = {tile["id"]: tile for tile in source["tiles"]}
    for change in data["tiles"]:
        if change["id"] not in by_id:
            raise ValueError("Cannot edit an unknown tile ID")
        tile = by_id[change["id"]]
        if "patch" in change: tile["source"] = sprite.edit_source(tile["source"], change["patch"])
        for key in ("solid", "terrain", "corners"):
            if key in change: tile[key] = change[key]
    if "cells" in data: source["cells"] = data["cells"]
    if "recolor" in data:
        for tile in source["tiles"]:
            tile["source"] = sprite.edit_source(tile["source"], {"schema_version": 1, "operations": [{"op": "recolor", **data["recolor"]}]})
    for key in ("collision_layer", "collision_mask"):
        if key in data: source[key] = data[key]
    provenance = {"method": "tileset-edit", "parent_revision_hash": parent["revision_hash"],
                  "patch_sha256": sprite.digest(sprite.encoded({key: value for key, value in data.items() if key not in {"apply", "output"}})),
                  "license": parent["manifest"]["provenance"].get("license")}
    return save(context, data, tileset.make_revision(source, provenance), tileset.KIND)


def tileset_inspect(context, data):
    revision = tileset.load_revision(context.path(data["bundle"]))
    source = revision["source"]
    return {"name": source["name"], "revision_hash": revision["revision_hash"], "artifact_kind": "tileset",
            "terrains": source["terrains"], "tiles": [{key: value for key, value in tile.items() if key != "source"} for tile in source["tiles"]],
            "seams": tileset.seams(source), "preview": str(revision["path"] / "preview.html"),
            "tile_preview": str(revision["path"] / "preview.png"), "layout_preview": str(revision["path"] / "layout.png")}, []


def tileset_approve(context, data):
    return approve(context, data, tileset.load_revision)


def tileset_import(context, data):
    revision = tileset.load_revision(context.path(data["bundle"]))
    report = tileset.seams(revision["source"])
    if report["mismatch_count"] or report["layout_terrain_mismatches"]:
        raise ValueError("Fix compatible-edge pixel mismatches and layout terrain mismatches before importing")
    return importing(context, data, tileset.load_revision, tileset_outputs)


def save(context, data, files, kind="sprite"):
    output = context.path(data["output"])
    result = store.save_revision(output, files, data.get("apply", False), kind=kind)
    return result, [output / name for name in files]


def approve(context, data, loader):
    bundle = context.path(data["bundle"])
    result = store.approve_revision(bundle, data["revision_hash"], data["reviewer"], data.get("apply", False), loader=loader)
    return result, [] if result["action"] == "keep_approval" else [bundle / "approval.json"]


def importing(context, data, loader, output_builder):
    result = store.import_revision(context.path(data["bundle"]), context.root, data.get("name"), data.get("destination"), data.get("apply", False), loader=loader, output_builder=output_builder)
    return result, [context.path(path) for path in [*result["create"], result["update"]]]
