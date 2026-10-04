"""
Owner-gated cookie / secret vault for tier-1 Reach channels.

Secrets never leave owner-authenticated endpoints. Status APIs only return
booleans (configured or not), never values.

Storage: JSON file (default next to providers / under workspace).
Optional obfuscation with a key derived from PARADOX_OWNER_KEY so a casual
file read is not plain-text (not a substitute for volume permissions).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

import config

_lock = threading.Lock()

PLATFORM_FIELDS: dict[str, list[str]] = {
    "twitter": ["auth_token", "ct0"],
    "reddit": ["cookie"],
}

_VAULT_FILE = Path(
    os.getenv(
        "PARADOX_VAULT_FILE",
        str(Path(config.PROVIDERS_FILE).parent / "vault.json"),
    )
)


def _derive_key() -> bytes:
    raw = (config.OWNER_KEY or "paradox-local-vault").encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", raw, b"paradox-vault-v1", 120_000, dklen=32)


def _obfuscate(plain: str) -> str:
    key = _derive_key()
    data = plain.encode("utf-8")
    out = bytes(b ^ key[i % len(key)] for i, b in enumerate(data))
    return "v1:" + base64.urlsafe_b64encode(out).decode("ascii")


def _deobfuscate(blob: str) -> str:
    if not blob.startswith("v1:"):
        return blob
    raw = base64.urlsafe_b64decode(blob[3:].encode("ascii"))
    key = _derive_key()
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(raw)).decode("utf-8")


def _path() -> Path:
    return _VAULT_FILE


def _load() -> dict[str, Any]:
    path = _path()
    if not path.exists():
        return {"platforms": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"platforms": {}}
        data.setdefault("platforms", {})
        return data
    except (OSError, json.JSONDecodeError):
        return {"platforms": {}}


def _save(data: dict[str, Any]) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def status() -> dict[str, Any]:
    with _lock:
        data = _load()
    platforms = data.get("platforms") or {}
    out: dict[str, Any] = {}
    for name, fields in PLATFORM_FIELDS.items():
        entry = platforms.get(name) or {}
        secrets = entry.get("secrets") or {}
        configured = all(bool(secrets.get(f)) for f in fields)
        out[name] = {
            "configured": configured,
            "fields": fields,
            "updated_at": entry.get("updated_at"),
        }
    return {
        "platforms": out,
        "vault_file": str(_path()),
        "owner_gated": True,
    }


def get_secrets(platform: str) -> dict[str, str]:
    platform = (platform or "").strip().lower()
    if platform not in PLATFORM_FIELDS:
        raise ValueError(f"unknown platform: {platform}")
    with _lock:
        data = _load()
        entry = (data.get("platforms") or {}).get(platform) or {}
        raw = entry.get("secrets") or {}
    return {k: _deobfuscate(v) for k, v in raw.items() if isinstance(v, str) and v}


def set_secrets(platform: str, secrets: dict[str, str]) -> dict[str, Any]:
    platform = (platform or "").strip().lower()
    if platform not in PLATFORM_FIELDS:
        raise ValueError(f"unknown platform: {platform}")
    allowed = set(PLATFORM_FIELDS[platform])
    cleaned: dict[str, str] = {}
    for k, v in (secrets or {}).items():
        if k not in allowed:
            continue
        val = (v or "").strip()
        if val:
            cleaned[k] = _obfuscate(val)
    if not cleaned:
        raise ValueError(f"no valid fields for {platform}; expected {sorted(allowed)}")
    import time

    with _lock:
        data = _load()
        platforms = data.setdefault("platforms", {})
        prev = platforms.get(platform) or {}
        prev_secrets = dict(prev.get("secrets") or {})
        prev_secrets.update(cleaned)
        platforms[platform] = {
            "secrets": prev_secrets,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        _save(data)
    return status()["platforms"][platform]


def clear_platform(platform: str) -> dict[str, Any]:
    platform = (platform or "").strip().lower()
    if platform not in PLATFORM_FIELDS:
        raise ValueError(f"unknown platform: {platform}")
    with _lock:
        data = _load()
        platforms = data.setdefault("platforms", {})
        platforms.pop(platform, None)
        _save(data)
    return status()["platforms"].get(
        platform, {"configured": False, "fields": PLATFORM_FIELDS[platform]}
    )


def twitter_cookies() -> Optional[dict[str, str]]:
    s = get_secrets("twitter")
    token = s.get("auth_token") or ""
    ct0 = s.get("ct0") or ""
    if not token or not ct0:
        return None
    return {"auth_token": token, "ct0": ct0}


def reddit_cookie_header() -> Optional[str]:
    s = get_secrets("reddit")
    cookie = (s.get("cookie") or "").strip()
    return cookie or None
