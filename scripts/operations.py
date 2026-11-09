#!/usr/bin/env python3
"""One structured operation protocol for Daydream CLI and native OpenCode tools."""

import argparse
import json
import os
from pathlib import Path
import re
import signal
import sys

from asset_errors import ApprovalRequired, DependencyMissing, AssetConflict
from operation_registry import OPERATIONS, find, search, validate
from sprite_core import read_json
import asset_access


class ScopeError(PermissionError):
    pass


class Context:
    def __init__(self, project):
        self.root = Path(project).expanduser().resolve(strict=True)
        if not self.root.is_dir(): raise ValueError("The active project must be a directory")
        if self.root.name in {".git", ".aws", ".ssh", ".config"}: raise ScopeError("Sensitive configuration directories are not asset workspaces")

    def path(self, value):
        if not isinstance(value, str) or not value or len(value) > 4096 or any(ord(ch) < 32 for ch in value) or "\\" in value:
            raise ValueError("Expected a bounded project path without control characters")
        raw = Path(value).expanduser()
        if ".." in raw.parts: raise ScopeError("Path traversal is not allowed in project operations")
        path = raw if raw.is_absolute() else self.root / raw
        try:
            relative = path.relative_to(self.root)
            path.resolve().relative_to(self.root)
        except (ValueError, RuntimeError) as exc:
            raise ScopeError("Operation paths must remain inside the active project") from exc
        current = self.root
        for part in relative.parts:
            if part in {".git", ".ssh", ".aws", ".config"} or part == ".env" or part.startswith(".env."):
                raise ScopeError("Sensitive configuration paths are not asset operation inputs")
            current = current / part
            if current.is_symlink(): raise ScopeError("Symlink components are not allowed in operation paths")
        return path

    def relative(self, path):
        path = self.path(str(path))
        return path.relative_to(self.root).as_posix()


def values_at(value, field):
    if not field: return [value]
    head, *tail = field
    if head == "*":
        return [item for entry in value for item in values_at(entry, tail)]
    return values_at(value[head], tail) if head in value else []


def prepare(operation, data, context):
    validate(operation.schema, data)
    reads = set()
    for field, kind in operation.paths:
        for value in values_at(data, field.split(".")):
            path = context.path(value)
            if kind == "output": continue
            if kind == "file": reads.add(str(path)); continue
            if kind == 'dashboard_asset':
                if data['kind'] == 'image':
                    reads.add(str(path))
                    continue
                kind = {'sprite': 'static_bundle', 'animation': 'animation_bundle', 'tileset': 'tileset_bundle'}[data['kind']]
            names = {"source.json", "manifest.json", ".gdignore", "approval.json", "changes-requested.json"}
            if kind == "review_bundle":
                kind = {"sprite": "static_bundle", "animation": "animation_bundle", "tileset": "tileset_bundle"}[data["kind"]]
            if kind == "static_bundle": names |= {"sprite.png", "preview.png"}
            elif kind == "tileset_bundle": names |= {"atlas.png", "preview.png", "layout.png", "collisions.png", "seams.json", "preview.html"}
            elif kind == "animation_bundle":
                names |= {"spritesheet.png", "preview.html"}
                if path.is_dir():
                    # Enumerate names only before read authorization; never read
                    # a manifest to discover more files behind that permission.
                    with os.scandir(path) as entries:
                        for index, entry in enumerate(entries):
                            if index >= 256: raise ValueError("Revision directory has too many entries")
                            if re.fullmatch(r"[a-z][a-z0-9_-]{0,47}\.(motion|contact)\.png", entry.name): names.add(entry.name)
            else: raise ValueError("Unsupported catalog path authority")
            if path.is_dir():
                from review_core import feedback_filenames
                names.update(feedback_filenames(path))
            reads.update(str(context.path(str(path / name))) for name in names)
    reads.update(str(context.path(path)) for path in operation.project_reads)
    access = {"reads": sorted(reads), "writes": []}
    if operation.engine:
        access["engine_resolution"] = True
    if operation.discovery or data.get('strategy') == 'update':
        access['read_resolution'] = True
    return access


def failure(name, code, message, next_step, *, partial=False):
    return {"ok": False, "status": "needs_approval" if code == "approval_required" else "error", "operation": name,
            "error": {"code": code, "message": str(message), "retry": "no", "next": next_step, "partial_possible": partial}}


def artifacts(result, status):
    items = []
    for key, purpose, mime in (("preview", "review", "text/html" if str(result.get("preview", "")).endswith(".html") else "image/png"), ("spritesheet", "runtime_atlas", "image/png")):
        if isinstance(result.get(key), str): items.append({"path": result[key], "purpose": purpose, "mime": mime, "state": "planned" if status == "preview" else "available"})
    for clip in result.get("previews", []):
        for key, purpose in (("motion", "motion_preview"), ("contact_sheet", "contact_sheet")):
            items.append({"path": clip[key], "purpose": purpose, "mime": "image/png", "animation": clip["animation"], "state": "available"})
    return items


def execute(name, data, project, *, surface="cli", prepare_only=False, resolve_only=False, authorized=None):
    operation = find(name)
    if operation is None: return failure(name, "not_found", "Unknown Daydream operation", "Use daydream ops search to discover an existing operation.")
    writing = isinstance(data, dict) and data.get("apply") is True and operation.effect != "read"
    try:
        if surface == "native" and not operation.native:
            return failure(name, "unsupported", "Approval/feedback decisions are not written by model-facing tools", "Use the user /assets UI or explicitly authorized CLI review; do not self-approve.")
        context = Context(project)
        access = prepare(operation, data, context)
        if prepare_only:
            return {"ok": True, "status": "prepared", "operation": name, "access": access, "effect": operation.effect}
        reads = set(access["reads"])
        write_grants = None
        if surface in {"native", "review_ui"}:
            authorized = authorized or {"reads": [], "writes": []}
            if not isinstance(authorized, dict) or not {"reads", "writes"}.issubset(authorized) or set(authorized) - {"reads", "writes", "executables"}:
                raise ValueError("Invalid adapter authorization envelope")
            for paths in authorized.values():
                if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
                    raise ValueError("Authorization paths must be string arrays")
            if not reads.issubset(set(authorized["reads"])):
                raise PermissionError("Adapter must authorize all planned reads before execution")
            write_grants = set(authorized["writes"])
        if access.get('read_resolution'):
            if name.startswith('dashboard.'):
                from dashboard import discover_reads
            else:
                from asset_lifecycle import discover_reads
            with asset_access.grants(reads, set()):
                reads |= discover_reads(context, name, data)
            access['reads'] = sorted(reads)
            access.pop('read_resolution', None)
            if not resolve_only and surface in {'native', 'review_ui'} and not reads.issubset(set(authorized['reads'])):
                raise PermissionError("Authorize the additional managed asset reads before continuing")
        from asset_lifecycle import normalize_request
        data, context.display_name = normalize_request(name, data)
        with asset_access.grants(reads, write_grants if writing else set()):
            if operation.engine:
                from engine_selection import project_engine
                selected = project_engine(context, data)
                context.engine = selected['godot']
                context.engine_version = selected['expected_version']
                context.engine_selection = selected
                access.pop('engine_resolution', None)
                access['executables'] = [context.engine]
                if resolve_only:
                    return {"ok": True, "status": "resolved", "operation": name, "access": access, "engine": selected}
                if surface in {"native", "review_ui"} and not set(access['executables']).issubset(set(authorized.get('executables', []))):
                    raise PermissionError("Separate Godot serialization execution permission is required before preview or apply")
            elif resolve_only:
                return {"ok": True, "status": "resolved", "operation": name, "access": access}
            result, writes = operation.handler(context, data)
        access["writes"] = [str(context.path(str(path))) for path in writes]
        status = "done" if operation.effect == "read" or writing else "preview"
        return {"ok": True, "status": status, "operation": name, "result": result, "access": access,
                "artifacts": artifacts(result, status), "evidence": {"images_viewed": False, "motion_reviewed": False, "godot_run": operation.engine}}
    except DependencyMissing as exc:
        return failure(name, "dependency_missing", exc, "Enable the optional sprite environment using requirements-sprites.txt; no software was installed.")
    except ApprovalRequired as exc:
        return failure(name, "approval_required", exc, "Review and explicitly approve this exact revision before importing.")
    except ScopeError as exc:
        return failure(name, "outside_project", exc, "Use an authorized path inside the active project; do not bypass a permission denial through another adapter.")
    except (FileExistsError, AssetConflict) as exc:
        return failure(name, "conflict", exc, "Inspect the existing destination or lock and choose a new revision/name; never overwrite user work.", partial=writing)
    except FileNotFoundError as exc:
        return failure(name, "not_found", exc, "Inspect the source path and project metadata; do not create a replacement blindly.", partial=writing)
    except PermissionError as exc:
        return failure(name, "forbidden", exc, "Keep existing permissions; ask the user about the denied path.", partial=writing)
    except KeyboardInterrupt:
        return failure(name, "cancelled", "Operation cancelled", "Inspect possible partial new output before retrying.", partial=writing)
    except (ValueError, OSError, RuntimeError) as exc:
        return failure(name, "invalid_input", exc, "Use daydream ops describe for the input contract; inspect possible partial output before retrying.", partial=writing)


def protocol(request, project, surface="cli"):
    if not isinstance(request, dict) or set(request) - {"action", "op", "input", "query", "limit", "authorized"}:
        raise ValueError("Unsupported operation request envelope")
    action = request.get("action")
    if not isinstance(action, str): raise ValueError("Operation protocol action must be a string")
    if action == "catalog":
        return {"ok": True, "status": "done", "result": {"contract_version": 1, "operations": [operation.metadata() for operation in OPERATIONS]}}
    if action == "search":
        query, limit = request.get("query", ""), request.get("limit", 10)
        if not isinstance(query, str) or len(query) > 500 or type(limit) is not int or not 1 <= limit <= 50: raise ValueError("Search needs bounded query and limit 1–50")
        return {"ok": True, "status": "done", "result": {"operations": search(query, limit)}}
    if action == "describe":
        operation = find(request.get("op"))
        return {"ok": True, "status": "done", "result": {"operation": operation.metadata()}} if operation else failure(request.get("op"), "not_found", "Unknown operation", "Use daydream ops search.")
    if action in {"call", "prepare", "resolve"}:
        return execute(request.get("op"), request.get("input", {}), project, surface=surface, prepare_only=action == "prepare", resolve_only=action == "resolve", authorized=request.get("authorized"))
    raise ValueError("Unknown operation protocol action")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd(), help="active workspace; all operation paths are scoped here")
    commands = parser.add_subparsers(dest="command", required=True)
    searching = commands.add_parser("search")
    searching.add_argument("query", nargs="*", default=[])
    searching.add_argument("--limit", type=int, default=10)
    describing = commands.add_parser("describe")
    describing.add_argument("op")
    calling = commands.add_parser("call")
    calling.add_argument("op")
    inputs = calling.add_mutually_exclusive_group()
    inputs.add_argument("--input", default="{}")
    inputs.add_argument("--input-file", type=Path)
    calling.add_argument("--apply", action="store_true", help="explicitly request writes; JSON alone cannot enable CLI writes")
    rpc = commands.add_parser("rpc", help=argparse.SUPPRESS)
    surface = rpc.add_mutually_exclusive_group()
    surface.add_argument("--native", action="store_true")
    surface.add_argument("--review-ui", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.command == "rpc":
            raw = sys.stdin.buffer.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024: raise ValueError("Operation request exceeds 1 MiB")
            answer = protocol(json.loads(raw), args.project, "review_ui" if args.review_ui else "native" if args.native else "cli")
        elif args.command == "search": answer = protocol({"action": "search", "query": " ".join(args.query), "limit": args.limit}, args.project)
        elif args.command == "describe": answer = protocol({"action": "describe", "op": args.op}, args.project)
        else:
            data = read_json(args.input_file) if args.input_file else json.loads(args.input)
            operation = find(args.op)
            if operation and operation.effect != "read":
                validate(operation.schema, data)
                if data.get("apply") is True and not args.apply: raise ValueError("CLI writes require the explicit --apply flag, not only JSON apply:true")
                data = {**data, "apply": args.apply}
            answer = execute(args.op, data, args.project)
    except (ValueError, OSError, RuntimeError) as exc:
        answer = failure(None, "invalid_input", exc, "Check daydream ops --help and describe the operation.")
    except KeyboardInterrupt:
        answer = failure(None, "cancelled", "Operation cancelled", "Inspect possible partial output before retrying.", partial=True)
    print(json.dumps(answer, indent=2))
    return 0 if answer["ok"] else 1


def cancelled(*_):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, cancelled)
    sys.exit(main())
