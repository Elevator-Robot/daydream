"""Shared exact-revision feedback/status, used by CLI and the user review UI."""

from datetime import datetime, timezone
import json
import os

from asset_errors import ApprovalRequired, AssetConflict
from sprite_core import encoded, read_regular
import sprite_store as store

FEEDBACK_FILE = "changes-requested.json"


def load_feedback(revision):
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            data = json.loads(read_regular(FEEDBACK_FILE, 16384, dir_fd=fd, base=revision["path"]))
        except FileNotFoundError:
            return None
    finally:
        os.close(fd)
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("decision") != "changes_requested" or data.get("revision_hash") != revision["revision_hash"] or data.get("kind") != revision["manifest"]["kind"]:
        raise ValueError("Feedback does not match this exact revision; preserve the bundle and create a fresh revision")
    for key, limit in (("reviewer", 120), ("feedback", 4000), ("reviewed_at", 100)):
        if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > limit:
            raise ValueError("Invalid revision feedback record")
    return data


def ensure_no_changes(revision):
    if load_feedback(revision) is not None:
        raise ApprovalRequired("Changes were requested for this revision; create, review and approve a fresh revision before importing")


def status(revision):
    feedback = load_feedback(revision)
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        try:
            approval = json.loads(read_regular("approval.json", 65536, dir_fd=fd, base=revision["path"]))
        except FileNotFoundError:
            approval = None
    finally:
        os.close(fd)
    stale = False
    if approval is not None:
        try:
            store.validate_approval(revision, approval)
        except ApprovalRequired:
            stale = True
    return {"revision_hash": revision["revision_hash"], "kind": revision["manifest"]["kind"],
            "state": "changes_requested" if feedback else "approved" if approval and not stale else "unreviewed",
            "approval": None if stale else approval, "stale_approval": stale, "feedback": feedback}


def request_changes(bundle, revision_hash, reviewer, feedback, apply=False, *, loader):
    with store.review_lock(bundle, apply):
        revision = loader(bundle)
        if revision_hash != revision["revision_hash"]:
            raise ValueError("Feedback hash does not match the revision shown for review")
        if not isinstance(reviewer, str) or not reviewer.strip() or len(reviewer) > 120 or any(ord(ch) < 32 for ch in reviewer):
            raise ValueError("Reviewer must be a nonempty label of at most 120 characters")
        if not isinstance(feedback, str) or not feedback.strip() or len(feedback) > 4000 or any(ord(ch) < 32 and ch not in "\n\t" for ch in feedback):
            raise ValueError("Changes need nonempty feedback of at most 4000 characters")
        existing = load_feedback(revision)
        if existing:
            if existing["reviewer"] != reviewer or existing["feedback"] != feedback:
                raise AssetConflict("Feedback already exists; it is retained rather than overwritten")
            return {"action": "keep_feedback", "revision_hash": revision_hash}
        record = {"schema_version": 1, "kind": revision["manifest"]["kind"], "decision": "changes_requested",
                  "revision_hash": revision_hash, "reviewer": reviewer, "feedback": feedback,
                  "reviewed_at": datetime.now(timezone.utc).isoformat()}
        if apply:
            fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                store.write_new(fd, FEEDBACK_FILE, encoded(record), base=revision["path"])
            finally:
                os.close(fd)
        return {"action": "changes_requested" if apply else "would_request_changes", "revision_hash": revision_hash}
