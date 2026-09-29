from __future__ import annotations

from uuid import uuid4


def new_id(prefix: str) -> str:
    """Return an opaque, stable public identifier safe for filenames and CLI use."""
    if not prefix.isalpha() or not prefix.islower():
        raise ValueError("ID prefix must contain lowercase letters only")
    return f"{prefix}_{uuid4().hex}"

