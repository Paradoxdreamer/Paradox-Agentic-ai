"""
Paradox AI - workspace

Per-user sandboxed file storage. Each user id gets its own folder under
WORKSPACE_DIR, so multi-tenant mode keeps everyone's generated apps
separate. In single-tenant (default) mode everything just lives under
WORKSPACE_DIR/default -- transparent if you were using this before
multi-user support existed.
"""
from __future__ import annotations

import io
import re
import shutil
import zipfile
from pathlib import Path
from typing import List

import config

BASE = config.WORKSPACE_DIR


class WorkspaceError(RuntimeError):
    pass


def _sanitize_user(user_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", user_id or "default")
    return safe or "default"


def user_root(user_id: str = "default") -> Path:
    root = BASE / _sanitize_user(user_id)
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_path(relative: str, user_id: str = "default") -> Path:
    """Resolve a user-supplied relative path and make sure it can't escape that user's root."""
    root = user_root(user_id).resolve()
    candidate = (root / relative).resolve()
    if root not in candidate.parents and candidate != root:
        raise WorkspaceError(f"path '{relative}' escapes the workspace")
    return candidate


_safe_path = safe_path  # backwards-compat alias for earlier single-tenant code


def list_files(user_id: str = "default") -> List[str]:
    root = user_root(user_id)
    return sorted(
        str(p.relative_to(root))
        for p in root.rglob("*")
        if p.is_file() and ".snapshots" not in p.parts
    )


def read_file(relative: str, user_id: str = "default") -> str:
    path = safe_path(relative, user_id)
    if not path.is_file():
        raise WorkspaceError(f"no such file: {relative}")
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(relative: str, content: str, user_id: str = "default") -> None:
    path = safe_path(relative, user_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def delete_file(relative: str, user_id: str = "default") -> None:
    path = safe_path(relative, user_id)
    if path.is_file():
        path.unlink()


def import_zip(zip_bytes: bytes, subfolder: str = "", user_id: str = "default") -> List[str]:
    root = user_root(user_id)
    target_root = safe_path(subfolder, user_id) if subfolder else root
    target_root.mkdir(parents=True, exist_ok=True)
    extracted = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            dest = (target_root / member).resolve()
            if target_root.resolve() not in dest.parents and dest != target_root.resolve():
                continue  # zip-slip guard
            if member.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
            extracted.append(str(dest.relative_to(root)))
    return extracted


def export_zip(user_id: str = "default") -> bytes:
    root = user_root(user_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file() and ".snapshots" not in path.parts:
                zf.write(path, path.relative_to(root))
    buf.seek(0)
    return buf.read()


def clear(user_id: str = "default") -> None:
    """Remove all files except snapshots (used by rollback before restoring one)."""
    root = user_root(user_id)
    for p in root.iterdir():
        if p.name == ".snapshots":
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
