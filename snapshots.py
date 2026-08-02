"""
Paradox AI - snapshots

Zip-based checkpoints of a user's workspace, so a risky agent edit, a
pipeline run, or an auto-fix loop can be rolled back. Snapshots live in
<workspace>/<user>/.snapshots/ and are excluded from the normal file list
and export.
"""
from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional

import workspace


class SnapshotError(RuntimeError):
    pass


def _snap_dir(user_id: str) -> Path:
    d = workspace.user_root(user_id) / ".snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def create(user_id: str = "default", label: Optional[str] = None) -> dict:
    snap_dir = _snap_dir(user_id)
    ts = time.strftime("%Y%m%dT%H%M%S")
    raw_id = f"{ts}_{label}" if label else ts
    snap_id = "".join(c for c in raw_id if c.isalnum() or c in "_-")
    zip_path = snap_dir / f"{snap_id}.zip"

    data = workspace.export_zip(user_id)  # already excludes .snapshots
    zip_path.write_bytes(data)

    return {"id": snap_id, "label": label, "created": ts}


def list_snapshots(user_id: str = "default") -> List[dict]:
    snap_dir = _snap_dir(user_id)
    out = []
    for p in sorted(snap_dir.glob("*.zip"), reverse=True):
        out.append({"id": p.stem, "created": p.stem.split("_")[0]})
    return out


def rollback(snap_id: str, user_id: str = "default") -> None:
    snap_dir = _snap_dir(user_id)
    zip_path = snap_dir / f"{snap_id}.zip"
    if not zip_path.is_file():
        raise SnapshotError(f"no such snapshot: {snap_id}")
    data = zip_path.read_bytes()
    workspace.clear(user_id)
    workspace.import_zip(data, user_id=user_id)
