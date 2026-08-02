"""
Paradox AI - db

SQLite persistence for user accounts and credit usage, using the stdlib
sqlite3 module -- no extra dependency. Only touched when PARADOX_AUTH_MODE
is "accounts" (see auth.py); every other mode never imports this, so no
paradox.db file appears unless you actually turn accounts on.

This is intentionally the only thing backed by a real database so far --
workspaces, chat sessions, and snapshots are still file/memory-based (see
README's "what's next" notes). Accounts and credits were the piece that
actually needed transactional, durable storage.
"""
from __future__ import annotations

import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import config

DB_PATH = Path(config.WORKSPACE_DIR).parent / "paradox.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    password_salt TEXT,
    auth_provider TEXT NOT NULL,
    google_sub TEXT UNIQUE,
    display_name TEXT,
    is_creator INTEGER NOT NULL DEFAULT 0,
    unlimited_credits INTEGER NOT NULL DEFAULT 0,
    credits INTEGER NOT NULL DEFAULT 0,
    api_key TEXT UNIQUE NOT NULL,
    accepted_terms INTEGER NOT NULL DEFAULT 0,
    accepted_terms_at TEXT,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS usage_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    cost INTEGER NOT NULL,
    created_at TEXT NOT NULL
);
"""


@contextmanager
def _conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_schema() -> None:
    with _conn() as conn:
        conn.executescript(SCHEMA)


_ensure_schema()  # cheap + idempotent; runs once when this module is first imported


def _row(row) -> Optional[dict]:
    return dict(row) if row else None


def get_user(user_id: str) -> Optional[dict]:
    with _conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())


def get_user_by_email(email: str) -> Optional[dict]:
    with _conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone())


def get_user_by_google_sub(sub: str) -> Optional[dict]:
    with _conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE google_sub = ?", (sub,)).fetchone())


def get_user_by_api_key(api_key: str) -> Optional[dict]:
    with _conn() as conn:
        return _row(conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone())


def create_user(
    email: str,
    api_key: str,
    auth_provider: str,
    password_hash: Optional[str] = None,
    password_salt: Optional[str] = None,
    google_sub: Optional[str] = None,
    display_name: Optional[str] = None,
    is_creator: bool = False,
    starting_credits: int = 50,
    accepted_terms: bool = False,
) -> dict:
    uid = uuid.uuid4().hex
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
    with _conn() as conn:
        conn.execute(
            """INSERT INTO users
               (id, email, password_hash, password_salt, auth_provider, google_sub,
                display_name, is_creator, unlimited_credits, credits, api_key,
                accepted_terms, accepted_terms_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                uid, email.lower(), password_hash, password_salt, auth_provider, google_sub,
                display_name, int(is_creator), int(is_creator),
                0 if is_creator else starting_credits,
                api_key, int(accepted_terms), now if accepted_terms else None, now,
            ),
        )
    return get_user(uid)


def set_api_key(user_id: str, new_key: str) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET api_key = ? WHERE id = ?", (new_key, user_id))


def record_failed_login(email: str, lock_after: int = 5, lock_minutes: int = 15) -> None:
    """Bumps the failed-login counter and locks the account temporarily past the threshold."""
    with _conn() as conn:
        row = conn.execute(
            "SELECT failed_login_count FROM users WHERE email = ?", (email.lower(),)
        ).fetchone()
        if row is None:
            return
        count = row["failed_login_count"] + 1
        if count >= lock_after:
            locked_until = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + lock_minutes * 60)
            )
            conn.execute(
                "UPDATE users SET failed_login_count = ?, locked_until = ? WHERE email = ?",
                (count, locked_until, email.lower()),
            )
        else:
            conn.execute(
                "UPDATE users SET failed_login_count = ? WHERE email = ?", (count, email.lower())
            )


def reset_failed_login(email: str) -> None:
    with _conn() as conn:
        conn.execute(
            "UPDATE users SET failed_login_count = 0, locked_until = NULL WHERE email = ?",
            (email.lower(),),
        )


def is_locked(user: dict) -> bool:
    locked_until = user.get("locked_until")
    if not locked_until:
        return False
    return locked_until > time.strftime("%Y-%m-%dT%H:%M:%SZ")


def adjust_credits(user_id: str, delta: int) -> None:
    with _conn() as conn:
        conn.execute("UPDATE users SET credits = credits + ? WHERE id = ?", (delta, user_id))


def grant_unlimited(email: str) -> bool:
    with _conn() as conn:
        cur = conn.execute(
            "UPDATE users SET is_creator = 1, unlimited_credits = 1 WHERE email = ?",
            (email.lower(),),
        )
        return cur.rowcount > 0


def log_usage(user_id: str, kind: str, cost: int) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT INTO usage_log (user_id, kind, cost, created_at) VALUES (?, ?, ?, ?)",
            (user_id, kind, cost, time.strftime("%Y-%m-%dT%H:%M:%SZ")),
        )


def list_users() -> list[dict]:
    with _conn() as conn:
        return [_row(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()]
