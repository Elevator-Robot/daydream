"""Per-call logical file grants supplied by the native adapter, not user data."""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path


READS = ContextVar("daydream_reads", default=None)
WRITES = ContextVar("daydream_writes", default=None)


def check(path, allowed, action):
    if allowed is not None and str(Path(path).absolute()) not in allowed:
        raise PermissionError(f"{action} is not authorized for this operation: {path}")


def read(path):
    check(path, READS.get(), "Read")


def write(path):
    check(path, WRITES.get(), "Write")


def anchored(name, base, *, writing=False):
    allowed = WRITES.get() if writing else READS.get()
    if allowed is None:
        return
    if base is None:
        raise PermissionError("Managed file access is missing its logical base path")
    check(Path(base) / name, allowed, "Write" if writing else "Read")


@contextmanager
def grants(reads=None, writes=None):
    read_token, write_token = READS.set(reads), WRITES.set(writes)
    try:
        yield
    finally:
        READS.reset(read_token)
        WRITES.reset(write_token)
