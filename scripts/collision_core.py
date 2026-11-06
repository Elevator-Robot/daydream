"""Explicit bounded tile collision geometry; never inferred from artwork alpha."""

import copy
import math

PRESETS = ("none", "full", "slope_up_right", "slope_up_left", "platform")


def number(value, minimum, maximum, label, *, grid=False):
    if type(value) not in (int, float) or (type(value) is float and not math.isfinite(value)) or not minimum <= value <= maximum:
        raise ValueError(f"{label} must be a finite number in {minimum}–{maximum}")
    if grid and value * 2 != int(value * 2):
        raise ValueError(f"{label} must lie on the half-pixel grid")
    return value


def cross(a, b, c):
    return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])


def intersects(a, b, c, d):
    def on(a, b, p):
        return cross(a, b, p) == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
    return ((cross(a, b, c) * cross(a, b, d) < 0 and cross(c, d, a) * cross(c, d, b) < 0)
            or on(a, b, c) or on(a, b, d) or on(c, d, a) or on(c, d, b))


def validate_polygons(polygons, width, height):
    if not isinstance(polygons, list) or len(polygons) > 8:
        raise ValueError("A tile supports 0–8 explicit convex collision polygons")
    for polygon in polygons:
        if not isinstance(polygon, dict) or "points" not in polygon or set(polygon) - {"points", "one_way", "one_way_margin"}:
            raise ValueError("Collision polygon needs points and optional one_way/one_way_margin")
        if type(polygon.get("one_way", False)) is not bool:
            raise ValueError("Collision one_way must be Boolean")
        number(polygon.get("one_way_margin", 1), 0, 16, "One-way margin")
        points = polygon["points"]
        if not isinstance(points, list) or not 3 <= len(points) <= 16:
            raise ValueError("Each collision polygon needs 3–16 vertices")
        integer_points = []
        for point in points:
            if not isinstance(point, list) or len(point) != 2:
                raise ValueError("Collision points must be [x, y] pairs")
            x = number(point[0], 0, width, "Collision x", grid=True)
            y = number(point[1], 0, height, "Collision y", grid=True)
            integer_points.append((int(x*2), int(y*2)))
        if len(set(integer_points)) != len(integer_points):
            raise ValueError("Collision polygon vertices must be distinct; omit a repeated closing vertex")
        count = len(integer_points)
        for i in range(count):
            for j in range(i+1, count):
                if j == i+1 or (i == 0 and j == count-1):
                    continue
                if intersects(integer_points[i], integer_points[(i+1) % count], integer_points[j], integer_points[(j+1) % count]):
                    raise ValueError("Collision polygons cannot self-intersect or touch nonadjacent edges")
        turns = [cross(integer_points[i], integer_points[(i+1) % count], integer_points[(i+2) % count]) for i in range(count)]
        if not (all(turn > 0 for turn in turns) or all(turn < 0 for turn in turns)):
            raise ValueError("Collision polygons must be strictly convex with nonzero area; split concave shapes into convex pieces")
    return copy.deepcopy(polygons)


def effective_polygons(tile):
    if "collisions" in tile:
        return [{"points": copy.deepcopy(polygon["points"]), "one_way": polygon.get("one_way", False),
                 "one_way_margin": polygon.get("one_way_margin", 1)} for polygon in tile["collisions"]]
    if tile["solid"]:
        width, height = tile["source"]["width"], tile["source"]["height"]
        return [{"points": [[0, 0], [width, 0], [width, height], [0, height]], "one_way": False, "one_way_margin": 1}]
    return []


def from_preset(options, width, height):
    if not isinstance(options, dict) or set(options) - {"preset", "one_way", "one_way_margin", "thickness"} or options.get("preset") not in PRESETS:
        raise ValueError("Unknown collision preset or preset field")
    preset = options["preset"]
    if preset == "none":
        if set(options) != {"preset"}:
            raise ValueError("The none preset has no one-way or thickness settings")
        return []
    if "thickness" in options and preset != "platform":
        raise ValueError("Only the platform preset accepts thickness")
    thickness = number(options.get("thickness", 1), .5, height, "Platform thickness", grid=True)
    points = {
        "full": [[0, 0], [width, 0], [width, height], [0, height]],
        "slope_up_right": [[0, height], [width, 0], [width, height]],
        "slope_up_left": [[0, 0], [width, height], [0, height]],
        "platform": [[0, 0], [width, 0], [width, thickness], [0, thickness]],
    }[preset]
    return validate_polygons([{"points": points, "one_way": options.get("one_way", preset == "platform"),
                               "one_way_margin": options.get("one_way_margin", 1)}], width, height)


def edit_collision(tile, change):
    choices = [key for key in ("solid", "collisions", "collision_preset") if key in change]
    if len(choices) > 1:
        raise ValueError("Choose only one of solid, collisions or collision_preset per tile edit")
    if not choices:
        return
    if choices == ["solid"]:
        if type(change["solid"]) is not bool:
            raise ValueError("solid must be Boolean")
        tile.pop("collisions", None)
        tile["solid"] = change["solid"]
        return
    width, height = tile["source"]["width"], tile["source"]["height"]
    polygons = (from_preset(change["collision_preset"], width, height) if "collision_preset" in change
                else validate_polygons(change["collisions"], width, height))
    tile["solid"], tile["collisions"] = False, polygons


def summary(source):
    polygons = [polygon for tile in source["tiles"] for polygon in effective_polygons(tile)]
    return {"explicit_tiles": sum("collisions" in tile for tile in source["tiles"]),
            "polygon_count": len(polygons), "one_way_polygons": sum(polygon["one_way"] for polygon in polygons),
            "coordinate_system": "tile-local pixels, top-left origin; half-pixel grid",
            "solid_color": "yellow", "one_way_color": "cyan", "inferred_from_alpha": False}
