"""
Paradox AI - auth

Three modes, controlled by PARADOX_AUTH_MODE:

  "none"      (default) -- no auth, single "default" workspace. Exactly the
              original single-tenant behavior; nothing changes if you don't
              set this.
  "apikeys"   -- static keys from PARADOX_API_KEYS env var (the older
              multi-tenant mode: "key1:alice,key2:bob").
  "accounts"  -- real signup/login (email+password or Google), DB-backed,
              per-user credits. See accounts.py / db.py / credits.py.

Even in "accounts" mode this is intentionally simple: one long-lived API
key per user, no session expiry, no refresh tokens, no 2FA. That's a
reasonable bar for a small/trusted deployment -- harden it (short-lived
tokens, MFA, audit logging) before this sits in front of the open internet
with real users and real money on the line.
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, Query

import config

# Legacy static-key map, used only in "apikeys" mode.
_RAW = os.getenv("PARADOX_API_KEYS", "").strip()
_KEY_MAP: dict[str, str] = {}
if _RAW:
    for pair in _RAW.split(","):
        if ":" in pair:
            key, user = pair.split(":", 1)
            _KEY_MAP[key.strip()] = user.strip()

MULTI_TENANT = config.AUTH_MODE != "none"


def _resolve_accounts_key(key: Optional[str]) -> str:
    import db  # local import: db.py (and its sqlite file) only touched in "accounts" mode

    if not key:
        raise HTTPException(401, "missing X-API-Key header (sign up or log in first)")
    user = db.get_user_by_api_key(key)
    if not user:
        raise HTTPException(401, "invalid API key")
    return user["id"]


def get_current_user(x_api_key: Optional[str] = Header(default=None)) -> str:
    if config.AUTH_MODE == "none":
        return "default"
    if config.AUTH_MODE == "apikeys":
        if not x_api_key or x_api_key not in _KEY_MAP:
            raise HTTPException(401, "missing or invalid X-API-Key header")
        return _KEY_MAP[x_api_key]
    if config.AUTH_MODE == "accounts":
        return _resolve_accounts_key(x_api_key)
    raise HTTPException(500, f"unknown PARADOX_AUTH_MODE '{config.AUTH_MODE}'")


def get_current_user_flexible(
    x_api_key: Optional[str] = Header(default=None),
    api_key: Optional[str] = Query(default=None),
) -> str:
    """
    Same as get_current_user, but also accepts the key as a ?api_key= query
    param. Only used for routes loaded via <img>/<iframe> src (live
    preview), where the browser has no way to attach a custom header.
    """
    key = x_api_key or api_key
    if config.AUTH_MODE == "none":
        return "default"
    if config.AUTH_MODE == "apikeys":
        if not key or key not in _KEY_MAP:
            raise HTTPException(401, "missing or invalid API key (header or ?api_key=)")
        return _KEY_MAP[key]
    if config.AUTH_MODE == "accounts":
        return _resolve_accounts_key(key)
    raise HTTPException(500, f"unknown PARADOX_AUTH_MODE '{config.AUTH_MODE}'")
