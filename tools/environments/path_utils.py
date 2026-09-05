"""Path-component helpers shared by execution environment backends. Kept separate from the
base class so lazy backend imports do not depend on newly added exports from a large module
cached earlier in a long-lived process."""

from __future__ import annotations

import hashlib
import re


# A persistent sandbox's host directory is named after task_id, and that name
# then becomes the source half of a Docker bind spec or a writable Singularity
# overlay directory. Keep every backend on one collision-safe mapping.
_SANDBOX_DIR_UNSAFE_RE = re.compile(r"[^A-Za-z0-9._-]")
_SANDBOX_DIR_MAX_LEN = 128
_SANDBOX_DIR_HASH_LEN = 12


def sanitize_task_id_for_path(task_id: str) -> str:
    """Bind-mountable directory name for *task_id*'s sandbox. Already-safe names are returned
    verbatim (preserving existing sandbox locations); rewritten names carry a digest because
    substitution alone is not injective: ``a:b`` and ``a_b`` must not share state."""
    value = task_id if isinstance(task_id, str) else ""
    if not value:
        return "default"

    cleaned = _SANDBOX_DIR_UNSAFE_RE.sub("_", value)
    if (cleaned == value and len(value) <= _SANDBOX_DIR_MAX_LEN
            and value not in {".", ".."} and not value.endswith((".", " "))):
        return value

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()[:_SANDBOX_DIR_HASH_LEN]
    stem = cleaned[: _SANDBOX_DIR_MAX_LEN - _SANDBOX_DIR_HASH_LEN - 1].strip("._")
    return f"{stem or 'task'}-{digest}"


def bind_mount_args(src: str, dst: str, *, readonly: bool = False) -> list[str]:
    """``--mount`` args for a bind mount the caller derived itself (sandbox dirs, host cwd,
    credential and CA files). The short ``-v src:dst`` form splits on ``:``, so any colon in *src* —
    a ``TERMINAL_SANDBOX_DIR`` or host cwd containing one — is read as an extra spec field and the
    run dies with exit 125. :func:`sanitize_task_id_for_path` only covers the task-id path segment,
    not the rest of the path.

    Long-form parsing splits on ``,`` instead, so *src* must not contain a comma; callers pass
    derived paths. A user-authored ``-v`` spec stays in the short form — the user owns the whole
    string there, where a bare ``:`` is a separator rather than data.
    """
    spec = f"type=bind,src={src},dst={dst}"
    return ["--mount", f"{spec},readonly" if readonly else spec]
