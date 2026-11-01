"""Non-overwriting sprite revision storage, approval, and Godot import plans."""

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import uuid

from init_project import validate_document, validate_path
from sprite_core import NAME, digest, encoded, load_revision, read_regular


def write_new(directory_fd, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=directory_fd)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)


def save_revision(output, files, apply=False):
    if set(files) != {"source.json", "sprite.png", "preview.png", "manifest.json", ".gdignore"}:
        raise ValueError("Revision output must contain only the five managed bundle files")
    output = Path(output).expanduser().absolute()
    if os.path.lexists(output):
        raise ValueError(f"Revision destination already exists; choose a new version: {output}")
    for parent in output.parents:
        if os.path.lexists(parent) and not parent.is_dir():
            raise ValueError(f"Revision parent is not a directory: {parent}")
    if apply:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir()  # Exclusive: never adopt an existing revision directory.
        fd = os.open(output, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for name, data in files.items():
                write_new(fd, name, data)
        finally:
            os.close(fd)
    return {"action": "created" if apply else "would_create", "directory": str(output),
            "files": list(files), "revision_hash": digest(files["manifest.json"]),
            "preview": str(output / "preview.png")}


def approve_revision(bundle, revision_hash, reviewer, apply=False):
    revision = load_revision(bundle)
    if revision_hash != revision["revision_hash"]:
        raise ValueError("Approval hash does not match this exact revision and preview")
    if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120 or any(ord(ch) < 32 for ch in reviewer):
        raise ValueError("Reviewer must be a nonempty label, at most 120 characters")
    record = {"schema_version": 1, "revision_hash": revision_hash,
              "sprite_sha256": revision["manifest"]["files"]["sprite.png"],
              "preview_sha256": revision["manifest"]["files"]["preview.png"],
              "reviewer": reviewer, "reviewed_at": datetime.now(timezone.utc).isoformat()}
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            existing = read_regular("approval.json", 65536, dir_fd=fd)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            validate_approval(revision, json.loads(existing))
            return {"action": "keep_approval", "revision_hash": revision_hash}
        if apply:
            write_new(fd, "approval.json", encoded(record))
    finally:
        os.close(fd)
    return {"action": "approved" if apply else "would_approve", "revision_hash": revision_hash, "reviewer": reviewer}


def validate_approval(revision, approval):
    if not isinstance(approval, dict) or type(approval.get("schema_version")) is not int or approval["schema_version"] != 1:
        raise ValueError("Unsupported approval record")
    if approval.get("revision_hash") != revision["revision_hash"] or any(
        approval.get(field) != revision["manifest"]["files"][name]
        for field, name in (("sprite_sha256", "sprite.png"), ("preview_sha256", "preview.png"))
    ):
        raise ValueError("Approval is stale; preview and approve the new revision")
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


def import_revision(bundle, project, name=None, destination=None, apply=False):
    revision = load_revision(bundle)
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            approval = json.loads(read_regular("approval.json", 65536, dir_fd=fd))
        except FileNotFoundError as exc:
            raise ValueError("Import requires explicit approval of this revision and preview") from exc
    finally:
        os.close(fd)
    validate_approval(revision, approval)
    project = Path(project).expanduser().resolve(strict=True)
    if not (project / "project.godot").is_file():
        raise ValueError("Import target must be a Godot project root")
    asset_name = revision["source"]["name"] if name is None else name
    if not isinstance(asset_name, str) or not NAME.fullmatch(asset_name):
        raise ValueError("Import name must be a lowercase asset slug")
    root = os.open(project, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    metadata = None
    lock = None
    temporary = None
    try:
        try:
            metadata = os.open(".daydream", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root)
        except FileNotFoundError as exc:
            raise ValueError("Initialize this game's .daydream configuration before importing") from exc
        config_bytes = read_regular("config.json", 1024 * 1024, dir_fd=metadata)
        index_bytes = read_regular("assets.json", 1024 * 1024, dir_fd=metadata)
        validate_document(project, "config.json", config_bytes.decode("utf-8"))
        validate_document(project, "assets.json", index_bytes.decode("utf-8"))
        config, index = json.loads(config_bytes), json.loads(index_bytes)
        asset_dir = relative_directory(project, destination if destination is not None else config["paths"]["assets"] + "/sprites")
        source_dir = relative_directory(project, config["paths"]["sources"] + "/sprites")
        texture = asset_dir + "/" + asset_name + ".png"
        scene = asset_dir + "/" + asset_name + ".tscn"
        source = source_dir + "/" + asset_name + ".json"
        scene_text = ('[gd_scene load_steps=2 format=3]\n\n'
                      '[ext_resource type="Texture2D" path=' + json.dumps("res://" + texture, ensure_ascii=False) + ' id="1"]\n\n'
                      '[node name=' + json.dumps(asset_name) + ' type="Sprite2D"]\n'
                      'texture_filter = 1\ntexture = ExtResource("1")\n')
        outputs = {texture: revision["files"]["sprite.png"], scene: scene_text.encode("utf-8"), source: revision["files"]["source.json"]}
        if len(outputs) != 3:
            raise ValueError("Runtime and editable-source output paths overlap")
        for relative in [*outputs, texture + ".import", scene + ".uid"]:
            with parent_fd(root, relative) as (directory, leaf):
                if directory is None:
                    continue
                try:
                    os.stat(leaf, dir_fd=directory, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                raise ValueError(f"Refusing to replace existing asset: {relative}; use a new --name")
        if any(record.get("name") == asset_name and record.get("kind") == "sprite" for record in index["assets"]):
            raise ValueError("Asset name already exists in the manifest; use a new --name")
        record = {"schema_version": 1, "kind": "sprite", "name": asset_name,
                  "revision_hash": revision["revision_hash"], "paths": {"texture": texture, "scene": scene, "source": source},
                  "sha256": {relative: digest(data) for relative, data in outputs.items()},
                  "provenance": revision["manifest"].get("provenance"), "approval": approval}
        index["assets"].append(record)
        updated = encoded(index)
        if len(updated) > 1024 * 1024:
            raise ValueError("Updated asset manifest would exceed its size limit")
        plan = {"action": "imported" if apply else "would_import", "project": str(project),
                "create": list(outputs), "update": ".daydream/assets.json", "revision_hash": revision["revision_hash"]}
        if not apply:
            return plan
        lock_fd = os.open(".sprites.lock", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=metadata)
        lock = os.fstat(lock_fd).st_ino
        with os.fdopen(lock_fd, "wb") as stream:
            stream.write(encoded({"tool": "daydream-sprites", "pid": os.getpid()}))
        if read_regular("assets.json", 1024 * 1024, dir_fd=metadata) != index_bytes or read_regular("config.json", 1024 * 1024, dir_fd=metadata) != config_bytes:
            raise ValueError("Project metadata changed during import planning; preview again")
        for relative, data in outputs.items():
            with parent_fd(root, relative, create=True) as (directory, leaf):
                write_new(directory, leaf, data)
        candidate = ".sprites-" + uuid.uuid4().hex + ".tmp"
        write_new(metadata, candidate, updated)
        temporary = candidate
        if read_regular("assets.json", 1024 * 1024, dir_fd=metadata) != index_bytes or read_regular("config.json", 1024 * 1024, dir_fd=metadata) != config_bytes:
            raise ValueError("Asset manifest changed concurrently; new files were left for inspection")
        os.replace(temporary, "assets.json", src_dir_fd=metadata, dst_dir_fd=metadata)
        temporary = None
        return plan
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
