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


_safe_path = safe_path


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


MAX_ZIP_FILES = 80
MAX_ZIP_MEMBER = 8 * 1024 * 1024
MAX_ZIP_TOTAL = 40 * 1024 * 1024


def import_zip(zip_bytes: bytes, subfolder: str = "", user_id: str = "default") -> List[str]:
    if len(zip_bytes) > MAX_ZIP_TOTAL:
        raise WorkspaceError("zip is too large")
    root = user_root(user_id)
    target_root = safe_path(subfolder, user_id) if subfolder else root
    target_root.mkdir(parents=True, exist_ok=True)
    extracted = []
    total = 0
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if len(names) > MAX_ZIP_FILES:
            raise WorkspaceError(f"zip has too many entries (max {MAX_ZIP_FILES})")
        for member in names:
            dest = (target_root / member).resolve()
            if target_root.resolve() not in dest.parents and dest != target_root.resolve():
                continue
            if member.endswith("/"):
                dest.mkdir(parents=True, exist_ok=True)
                continue
            info = zf.getinfo(member)
            if info.file_size > MAX_ZIP_MEMBER:
                raise WorkspaceError(f"zip member '{member}' is too large")
            total += info.file_size
            if total > MAX_ZIP_TOTAL:
                raise WorkspaceError("uncompressed zip contents exceed the size limit")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as out:
                remaining = info.file_size
                while remaining > 0:
                    chunk = src.read(min(65536, remaining))
                    if not chunk:
                        break
                    out.write(chunk)
                    remaining -= len(chunk)
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
    root = user_root(user_id)
    for p in root.iterdir():
        if p.name == ".snapshots":
            continue
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
