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
MAX_ZIP_TOTAL = 32 * 1024 * 1024


def import_zip(zip_bytes: bytes, user_id: str = "default") -> list[str]:
    root = user_root(user_id)
    extracted: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = [n for n in zf.namelist() if not n.endswith("/")]
        if len(names) > MAX_ZIP_FILES:
            raise WorkspaceError(f"zip has too many entries (max {MAX_ZIP_FILES})")
        total = 0
        for name in names:
            info = zf.getinfo(name)
            if info.file_size > MAX_ZIP_MEMBER:
                raise WorkspaceError(f"zip member too large: {name}")
            total += info.file_size
            if total > MAX_ZIP_TOTAL:
                raise WorkspaceError("zip total size too large")
            # path traversal guard
            target = safe_path(name, user_id)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(target, "wb") as dst:
                remaining = info.file_size
                while remaining > 0:
                    chunk = src.read(min(65536, remaining))
                    if not chunk:
                        break
                    dst.write(chunk)
                    remaining -= len(chunk)
            extracted.append(str(target.relative_to(root)))
    return extracted


def export_zip(user_id: str = "default") -> bytes:
    root = user_root(user_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in root.rglob("*"):
            if path.is_file() and ".snapshots" not in path.parts:
                zf.write(path, arcname=str(path.relative_to(root)))
    return buf.getvalue()


MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
ALLOWED_UPLOAD_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico",
    ".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v",
    ".mp3", ".wav", ".ogg", ".m4a",
    ".pdf", ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm",
    ".py", ".js", ".ts", ".tsx", ".css", ".yml", ".yaml", ".toml",
    ".zip", ".tar", ".gz",
}


def _safe_filename(name: str) -> str:
    base = Path(name or "upload.bin").name
    base = re.sub(r"[^a-zA-Z0-9._\- ]", "_", base).strip(" ._") or "upload.bin"
    if len(base) > 180:
        stem, suf = Path(base).stem[:140], Path(base).suffix[:20]
        base = stem + suf
    return base


def save_upload(
    filename: str,
    data: bytes,
    user_id: str = "default",
    subdir: str = "uploads",
) -> dict:
    """Save a binary upload under workspace/{user}/uploads/."""
    if not data:
        raise WorkspaceError("empty upload")
    if len(data) > MAX_UPLOAD_BYTES:
        raise WorkspaceError(f"file too large (max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB)")
    safe = _safe_filename(filename)
    ext = Path(safe).suffix.lower()
    if ext and ext not in ALLOWED_UPLOAD_EXT:
        raise WorkspaceError(f"file type '{ext}' not allowed")
    rel = f"{subdir.rstrip('/')}/{safe}" if subdir else safe
    path = safe_path(rel, user_id)
    if path.exists():
        stem, suf = path.stem, path.suffix
        n = 1
        while path.exists():
            path = path.with_name(f"{stem}_{n}{suf}")
            n += 1
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    image_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".ico"}
    video_ext = {".mp4", ".webm", ".mov", ".mkv", ".avi", ".m4v"}
    audio_ext = {".mp3", ".wav", ".ogg", ".m4a"}
    if ext in image_ext:
        kind = "image"
    elif ext in video_ext:
        kind = "video"
    elif ext in audio_ext:
        kind = "audio"
    else:
        kind = "file"
    rel_out = str(path.relative_to(user_root(user_id))).replace("\\", "/")
    return {
        "path": rel_out,
        "size": len(data),
        "kind": kind,
        "filename": path.name,
    }
