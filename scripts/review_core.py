"""Shared exact-revision feedback/status, used by CLI and the user review UI."""

from datetime import datetime, timezone
import json
import os
import re

from asset_errors import ApprovalRequired
from sprite_core import digest, encoded, read_regular
import sprite_store as store

FEEDBACK_FILE = "changes-requested.json"
FOLLOWUP = re.compile(r"changes-requested\.[0-9a-f]{64}\.json\Z")
MAX_NOTES = 32
MAX_FEEDBACK_BYTES = 256 * 1024


def feedback_filenames(directory):
    """Enumerate names only (also accepts an open directory fd); no content reads."""
    names = []
    with os.scandir(directory) as entries:
        for index, entry in enumerate(entries):
            if index >= 512:
                raise ValueError("Too many files in this revision; inspect it before reviewing")
            if FOLLOWUP.fullmatch(entry.name):
                names.append(entry.name)
    if len(names) >= MAX_NOTES:
        raise ValueError("This revision has too many feedback notes; create a revised candidate")
    return [FEEDBACK_FILE, *sorted(names)]


def note_filename(revision, reviewer, feedback):
    identity = {"kind": revision["manifest"]["kind"], "revision_hash": revision["revision_hash"],
                "reviewer": reviewer, "feedback": feedback}
    return "changes-requested." + digest(encoded(identity)) + ".json"


def validate_feedback(data, revision):
    if not isinstance(data, dict) or type(data.get("schema_version")) is not int or data["schema_version"] != 1 or data.get("decision") != "changes_requested" or data.get("revision_hash") != revision["revision_hash"] or data.get("kind") != revision["manifest"]["kind"]:
        raise ValueError("Feedback does not match this exact revision; preserve the bundle and create a fresh revision")
    for key, limit in (("reviewer", 120), ("feedback", 4000), ("reviewed_at", 100)):
        if not isinstance(data.get(key), str) or not data[key].strip() or len(data[key]) > limit:
            raise ValueError("Invalid revision feedback record")
    return data


def load_feedback(revision):
    notes = []
    total = 0
    fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for name in feedback_filenames(fd):
            try:
                raw = read_regular(name, 65536, dir_fd=fd, base=revision["path"])
            except FileNotFoundError:
                if name == FEEDBACK_FILE: continue
                raise ValueError("Feedback changed while opening this review; reopen the candidate")
            total += len(raw)
            if total > MAX_FEEDBACK_BYTES:
                raise ValueError("This version's feedback history is too large; preserve it and prepare a revised candidate")
            note = validate_feedback(json.loads(raw), revision)
            if name != FEEDBACK_FILE and name != note_filename(revision, note['reviewer'], note['feedback']):
                raise ValueError("A feedback note does not match its recorded identity")
            notes.append(note)
    finally:
        os.close(fd)
    if not notes:
        return None
    # Preserve the original single-record fields for callers, and expose the
    # complete ordered conversation. An orphan follow-up still blocks approval.
    first = notes[0]
    notes.sort(key=lambda note: (note['reviewed_at'], note['reviewer'], note['feedback']))
    return {**first, "notes": notes}


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
        notes = existing['notes'] if existing else []
        if any(note['reviewer'] == reviewer and note['feedback'] == feedback for note in notes):
            return {"action": "keep_feedback", "revision_hash": revision_hash, "note_count": len(notes)}
        record = {"schema_version": 1, "kind": revision["manifest"]["kind"], "decision": "changes_requested",
                   "revision_hash": revision_hash, "reviewer": reviewer, "feedback": feedback,
                   "reviewed_at": datetime.now(timezone.utc).isoformat()}
        if len(notes) >= MAX_NOTES or sum(len(encoded(note)) for note in [*notes, record]) > MAX_FEEDBACK_BYTES:
            raise ValueError("This candidate has a long feedback history. Ask Daydream to make a revised candidate; previous notes are kept")
        filename = note_filename(revision, reviewer, feedback) if existing else FEEDBACK_FILE
        if apply:
            fd = os.open(revision["path"], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                store.write_new(fd, filename, encoded(record), base=revision["path"])
            finally:
                os.close(fd)
        return {"action": "changes_requested" if apply else "would_request_changes", "revision_hash": revision_hash,
                "file": filename, "note_count": len(notes) + 1}
