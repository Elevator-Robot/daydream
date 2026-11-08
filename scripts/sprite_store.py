"""Non-overwriting sprite revision storage, approval, and Godot import plans."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from asset_errors import ApprovalRequired, AssetConflict
import asset_access

from init_project import validate_document, validate_path
from sprite_core import NAME, digest, encoded, load_revision, read_regular


def write_new(directory_fd, name, data, *, base=None, logical_path=None):
    if logical_path is not None: asset_access.write(logical_path)
    else: asset_access.anchored(name, base, writing=True)
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=directory_fd)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def save_revision(output, files, apply=False, *, kind="sprite"):
    if kind == "sprite":
        expected = {"source.json", "sprite.png", "preview.png", "manifest.json", ".gdignore"}
    elif kind == "sprite_animation":
        from animation_core import artifact_names, validate_source
        source = validate_source(json.loads(files["source.json"]))
        expected = artifact_names(source) | {"manifest.json", ".gdignore"}
    elif kind == "tileset":
        from tileset_core import artifact_names, validate_source
        source = validate_source(json.loads(files["source.json"]))
        expected = artifact_names(source) | {"manifest.json", ".gdignore"}
    else:
        raise ValueError("Unsupported revision bundle kind")
    if set(files) != expected:
        raise ValueError("Revision output must contain only the managed bundle files")
    output = Path(output).expanduser().absolute()
    if os.path.lexists(output):
        raise AssetConflict(f"Revision destination already exists; choose a new version: {output}")
    for parent in output.parents:
        if os.path.lexists(parent) and not parent.is_dir():
            raise ValueError(f"Revision parent is not a directory: {parent}")
    if apply:
        for name in files: asset_access.write(output / name)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()  # Exclusive: never adopt an existing revision directory.
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name, data in files.items():
                write_new(fd, name, data, base=output)
        finally:
            os.close(fd)
    return {"action": "created" if apply else "would_create", "directory": str(output),
            "files": list(files), "revision_hash": digest(files["manifest.json"]),
            "preview": str(output / ("preview.html" if kind in ("sprite_animation", "tileset") else "preview.png"))}


def approval_identity(revision):
    if revision["manifest"].get("kind") in ("sprite_animation", "tileset"):
        return {"schema_version": 2, "kind": revision["manifest"]["kind"], "revision_hash": revision["revision_hash"],
                "files": revision["manifest"]["files"]}
    if revision["manifest"].get("kind") != "sprite":
        raise ValueError("Unsupported approval kind")
    return {"schema_version": 1, "revision_hash": revision["revision_hash"],
            "sprite_sha256": revision["manifest"]["files"]["sprite.png"],
            "preview_sha256": revision["manifest"]["files"]["preview.png"]}


@contextmanager
def review_lock(bundle, apply):
    """Serialize managed approval, feedback and import writes for one bundle."""
    if not apply or asset_access.WRITES.get() == set():
        yield
        return
    fd = os.open(bundle, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    inode = None
    try:
        lock = os.open(".review.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=fd)
        inode = os.fstat(lock).st_ino
        with os.fdopen(lock, "wb") as stream:
            stream.write(encoded({"pid": os.getpid(), "tool": "daydream-review"}))
        yield
    finally:
        if inode is not None:
            try:
                if os.stat(".review.lock", dir_fd=fd, follow_symlinks=False).st_ino == inode:
                    os.unlink(".review.lock", dir_fd=fd)
            except FileNotFoundError:
                pass
        os.close(fd)


def approve_revision(bundle, revision_hash, reviewer, apply=False, *, loader=load_revision):
    with review_lock(bundle, apply):
        return _approve_revision(bundle, revision_hash, reviewer, apply, loader=loader)


def _approve_revision(bundle, revision_hash, reviewer, apply=False, *, loader=load_revision):
    revision = loader(bundle)
    from review_core import ensure_no_changes
    ensure_no_changes(revision)
    if revision_hash != revision["revision_hash"]:
        raise ValueError("Approval hash does not match this exact revision and preview")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120 or any(ord(ch) < 32 for ch in reviewer):
        raise ValueError("Reviewer must be a nonempty label, at most 120 characters")
    record = {**approval_identity(revision), "reviewer": reviewer, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            existing = read_regular("approval.json", 65536, dir_fd=fd, base=revision["path"])
        except FileNotFoundError:
            existing = None
        if existing is not None:
            validate_approval(revision, json.loads(existing))
            return {"action": "keep_approval", "revision_hash": revision_hash}
        if apply:
            write_new(fd, "approval.json", encoded(record), base=revision["path"])
    finally:
        os.close(fd)
    return {"action": "approved" if apply else "would_approve", "revision_hash": revision_hash, "reviewer": reviewer}


def validate_approval(revision, approval):
    identity = approval_identity(revision)
    if not isinstance(approval, dict) or type(approval.get("schema_version")) is not int or approval["schema_version"] != identity["schema_version"]:
        raise ValueError("Unsupported approval record")
    if any(approval.get(key) != value for key, value in identity.items()):
        raise ApprovalRequired("Approval is stale; preview and approve the new revision")
    if not isinstance(approval.get("reviewer"), str) or not approval["reviewer"].strip() or not isinstance(approval.get("reviewed_at"), str):
        raise ValueError("Approval must record a reviewer and review date")


@contextmanager
def parent_fd(root_fd, relative, create=False):
    current = os.dup(root_fd)
    parts = Path(relative).parts
    try:
        for part in parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    yield None, parts[-1]
                    return
                try:
                    os.mkdir(part, dir_fd=current)
                except FileExistsError:
                    pass
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            os.close(current)
            current = child
        yield current, parts[-1]
    finally:
        os.close(current)


def relative_directory(project, value):
    validate_path(project, value)
    if any(ord(character) < 32 for character in value):
        raise ValueError("Asset paths cannot contain control characters")
    return value


def static_outputs(revision, asset_dir, source_dir, asset_name):
    texture = asset_dir + "/" + asset_name + ".png"
    scene = asset_dir + "/" + asset_name + ".tscn"
    source = source_dir + "/" + asset_name + ".json"
    scene_text = ('[gd_scene load_steps=2 format=3]\n\n'
                  '[ext_resource type="Texture2D" path=' + json.dumps("res://" + texture, ensure_ascii=False) + ' id="1"]\n\n'
                  '[node name=' + json.dumps(asset_name) + ' type="Sprite2D"]\n'
                  'texture_filter = 1\ntexture = ExtResource("1")\n')
    return ({texture: revision["files"]["sprite.png"], scene: scene_text.encode("utf-8"), source: revision["files"]["source.json"]},
            {"texture": texture, "scene": scene, "source": source}, [texture + ".import", scene + ".uid"])


def import_revision(bundle, project, name=None, destination=None, apply=False, *, loader=load_revision, output_builder=static_outputs, revision_hash=None, plan_hash=None, strategy="new", target=None):
    with review_lock(bundle, apply):
        return _import_revision(bundle, project, name, destination, apply, loader=loader, output_builder=output_builder, revision_hash=revision_hash, plan_hash=plan_hash, strategy=strategy, target=target)


def _import_revision(bundle, project, name=None, destination=None, apply=False, *, loader=load_revision, output_builder=static_outputs, revision_hash=None, plan_hash=None, strategy="new", target=None):
    from asset_lifecycle import friendly_name, find_record, unique_import_name, record_paths, check_tile_identity
    if strategy not in {"new", "copy", "update"}:
        raise ValueError("Choose add a copy or update a managed asset")
    if strategy == "update" and (not isinstance(target, str) or not NAME.fullmatch(target)):
        raise ValueError("Select the registered asset to update")
    if strategy == "update" and apply and not plan_hash:
        raise ValueError("Review the update plan first; applying an update needs its exact plan hash")
    revision = loader(bundle)
    from review_core import ensure_no_changes
    ensure_no_changes(revision)
    if revision_hash is not None and revision_hash != revision["revision_hash"]:
        raise ValueError("Import revision changed since review; inspect the new candidate before applying")
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            approval = json.loads(read_regular("approval.json", 65536, dir_fd=fd, base=revision["path"]))
        except FileNotFoundError as exc:
            raise ApprovalRequired("Import requires explicit approval of this revision and preview") from exc
    finally:
        os.close(fd)
    validate_approval(revision, approval)
    project = Path(project).expanduser().resolve(strict=True)
    if not (project / "project.godot").is_file():
        raise ValueError("Import target must be a Godot project root")
    display_name, asset_name = friendly_name(revision["manifest"].get("provenance", {}).get("display_name", revision["source"]["name"]) if name is None else name)
    root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    metadata = None
    lock = None
    temporary = None
    archive = None
    try:
        try:
            metadata = os.open(".daydream", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        except FileNotFoundError as exc:
            raise ValueError("Initialize this game's .daydream configuration before importing") from exc
        metadata_path = project / ".daydream"
        config_bytes = read_regular("config.json", 1024 * 1024, dir_fd=metadata, base=metadata_path)
        index_bytes = read_regular("assets.json", 1024 * 1024, dir_fd=metadata, base=metadata_path)
        validate_document(project, "config.json", config_bytes.decode("utf-8"))
        validate_document(project, "assets.json", index_bytes.decode("utf-8"))
        config, index = json.loads(config_bytes), json.loads(index_bytes)
        previous = find_record(index, target) if strategy == "update" else None
        if strategy == "update" and (previous is None or previous.get('kind') != revision['manifest']['kind']):
            raise AssetConflict("That asset is not registered as the same type. Add a separate copy instead")
        category = "/tilesets" if revision["manifest"]["kind"] == "tileset" else "/sprites"
        asset_dir = relative_directory(project, destination if destination is not None else config["paths"]["assets"] + category)
        source_dir = relative_directory(project, config["paths"]["sources"] + category)
        old_files = {}
        if previous is not None:
            from operations import Context
            previous_paths = record_paths(Context(project), previous)
            asset_name = previous['name']
            display_name = previous.get('display_name', display_name)
            if destination is not None or name is not None:
                raise ValueError("An update keeps stable names and destinations. Add a copy to rename or relocate")
            asset_dir = relative_directory(project, str(Path(previous_paths['texture']).parent))
            source_dir = relative_directory(project, str(Path(previous_paths['source']).parent))
            for relative in previous_paths.values():
                with parent_fd(root, relative) as (directory, leaf):
                    if directory is None: raise AssetConflict("An imported file is missing; add a separate copy or restore it first")
                    old_files[relative] = read_regular(leaf, 32 * 1024 * 1024, dir_fd=directory, base=project / Path(relative).parent)
                if digest(old_files[relative]) != previous['sha256'][relative]:
                    raise AssetConflict(f"Modified outside Daydream: {relative}. Your edits are protected; add a separate copy instead")
            check_tile_identity(old_files[previous_paths['source']], revision)
        elif strategy == "copy":
            asset_name = unique_import_name(project, index, display_name, asset_dir, source_dir)
        outputs, paths, reserved = output_builder(revision, asset_dir, source_dir, asset_name)
        if len(outputs) != len(paths):
            raise ValueError("Runtime and editable-source output paths overlap")
        if previous is not None and paths != previous_paths:
            raise AssetConflict("This update changes the asset's file layout. Add a separate copy to keep existing references safe")
        for relative in ([] if previous is not None else [*outputs, *reserved]):
            with parent_fd(root, relative) as (directory, leaf):
                if directory is None:
                    continue
                try:
                    os.stat(leaf, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise AssetConflict(f"Refusing to replace existing asset: {relative}; use a new --name")
        if previous is None and any(record.get("name") == asset_name and record.get("kind") in ("sprite", "sprite_animation", "tileset") for record in index["assets"]):
            raise AssetConflict("Asset name already exists in the manifest; use a new --name")
        record = {"schema_version": 1, "kind": revision["manifest"]["kind"], "name": asset_name,
                  "display_name": display_name, "bundle": os.path.relpath(revision['path'], project),
                  "revision_hash": revision["revision_hash"], "paths": paths,
                  "sha256": {relative: digest(data) for relative, data in outputs.items()},
                  "provenance": revision["manifest"].get("provenance"), "approval": approval}
        if previous is not None:
            record = {**previous, **record}  # Preserve unrelated user registry annotations.
        if previous is None: index["assets"].append(record)
        else: index["assets"][index["assets"].index(previous)] = record
        updated = encoded(index)
        if len(updated) > 1024 * 1024:
            raise ValueError("Updated asset manifest would exceed its size limit")
        plan = {"action": "imported" if apply else "would_import", "project": str(project),
                "create": list(outputs) if previous is None else [], "replace": list(outputs) if previous is not None else [],
                "update": ".daydream/assets.json", "revision_hash": revision["revision_hash"], "asset_name": asset_name,
                "display_name": display_name, "strategy": strategy, "scene": paths.get('scene'),
                "summary": (f"Update {display_name} at its existing paths. Scenes that reference it will see the approved revision; a recovery snapshot is kept. Save and close editors for these files first: unsaved edits cannot be detected."
                            if previous else f"Add {display_name} as a separate asset. Existing scenes and gameplay are unchanged.")}
        plan["plan_hash"] = digest(encoded({"revision_hash": revision["revision_hash"], "outputs": {path: digest(data) for path, data in outputs.items()}, "metadata": digest(updated), "prior_index": digest(index_bytes)}))
        if plan_hash is not None and plan_hash != plan["plan_hash"]:
            raise ValueError("Import plan changed; review the new destinations/content before applying")
        backups = {}
        if previous is not None:
            archive = f".daydream/history/imports/{asset_name}/{plan['plan_hash']}"
            backups = {archive + '/files/' + relative: data for relative, data in old_files.items()}
            backups.update({archive + '/asset-record.json': encoded(previous), archive + '/assets-before.json': index_bytes,
                            archive + '/plan.json': encoded(plan), archive + '/.gdignore': b''})
            plan['history'] = archive
            plan['backup'] = list(backups) + [archive + '/applied.json']
            if os.path.lexists(project / archive):
                raise AssetConflict(f"An earlier update snapshot exists at {archive}. Inspect possible partial work before retrying")
        if not apply:
            return plan
        for relative in [*outputs, *plan.get('backup', []), ".daydream/assets.json"]: asset_access.write(project / relative)
        lock_fd = os.open(".sprites.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=metadata)
        lock = os.fstat(lock_fd).st_ino
        with os.fdopen(lock_fd, "wb") as stream:
            stream.write(encoded({"tool": "daydream-sprites", "pid": os.getpid()}))
        if read_regular("assets.json", 1024 * 1024, dir_fd=metadata, base=metadata_path) != index_bytes or read_regular("config.json", 1024 * 1024, dir_fd=metadata, base=metadata_path) != config_bytes:
            raise ValueError("Project metadata changed during import planning; preview again")
        def unchanged(relative, expected):
            with parent_fd(root, relative) as (directory, leaf):
                if directory is None or read_regular(leaf, 32 * 1024 * 1024, dir_fd=directory, base=project / Path(relative).parent) != expected:
                    raise AssetConflict(f"File changed during update: {relative}. Inspect the recovery snapshot before retrying")
        for relative, data in old_files.items(): unchanged(relative, data)
        for relative, data in backups.items():
            with parent_fd(root, relative, create=True) as (directory, leaf):
                write_new(directory, leaf, data, base=project / Path(relative).parent)
        for relative, data in outputs.items():
            with parent_fd(root, relative, create=True) as (directory, leaf):
                if previous is None:
                    write_new(directory, leaf, data, base=project / Path(relative).parent)
                else:
                    candidate = '.daydream-update-' + uuid.uuid4().hex + '.tmp'
                    try:
                        write_new(directory, candidate, data, logical_path=project / relative)
                        unchanged(relative, old_files[relative])
                        os.replace(candidate, leaf, src_dir_fd=directory, dst_dir_fd=directory)
                    finally:
                        try: os.unlink(candidate, dir_fd=directory)
                        except FileNotFoundError: pass
        candidate = ".sprites-" + uuid.uuid4().hex + ".tmp"
        write_new(metadata, candidate, updated, logical_path=metadata_path / "assets.json")
        temporary = candidate
        if read_regular("assets.json", 1024 * 1024, dir_fd=metadata, base=metadata_path) != index_bytes or read_regular("config.json", 1024 * 1024, dir_fd=metadata, base=metadata_path) != config_bytes:
            raise ValueError("Asset manifest changed concurrently; new files were left for inspection")
        asset_access.write(metadata_path / "assets.json")
        os.replace(temporary, "assets.json", src_dir_fd=metadata, dst_dir_fd=metadata)
        temporary = None
        if previous is not None:
            relative = archive + '/applied.json'
            with parent_fd(root, relative, create=True) as (directory, leaf):
                write_new(directory, leaf, encoded({'plan_hash': plan['plan_hash'], 'revision_hash': revision['revision_hash']}), base=project / Path(relative).parent)
        return plan
    except (OSError, ValueError) as exc:
        if archive and apply and lock is not None and not isinstance(exc, PermissionError):
            raise AssetConflict(f"Update did not finish cleanly. Inspect {archive} and the managed files before retrying; previous bytes are retained if snapshot creation completed. Details: {exc}") from exc
        raise
    finally:
        if metadata is not None:
            if temporary is not None:
                try:
                    os.unlink(temporary, dir_fd=metadata)
                except FileNotFoundError:
                    pass
            if lock is not None:
                try:
                    if os.stat(".sprites.lock", dir_fd=metadata, follow_symlinks=False).st_ino == lock:
                        os.unlink(".sprites.lock", dir_fd=metadata)
                except FileNotFoundError:
                    pass
            os.close(metadata)
        os.close(root)
