"""
Paradox AI - sessions

Lightweight in-memory conversation memory. A session holds the running
back-and-forth for one chat thread so agents get context on later turns
instead of answering each message cold.

This is process-memory only (resets on server restart). Fine for local/dev
use; swap _STORE for a real cache/db before running this multi-process.
"""
from __future__ import annotations

import uuid
from collections import defaultdict
from typing import List

MAX_TURNS = 20  # user+assistant pairs kept per session

_STORE: dict[str, List[dict]] = defaultdict(list)


def new_session_id() -> str:
    return uuid.uuid4().hex


def get_history(session_id: str) -> List[dict]:
    return _STORE[session_id]


def append(session_id: str, role: str, content: str) -> None:
    _STORE[session_id].append({"role": role, "content": content})
    if len(_STORE[session_id]) > MAX_TURNS * 2:
        _STORE[session_id] = _STORE[session_id][-MAX_TURNS * 2:]


def as_glm_messages(session_id: str, new_user_message: str) -> List[dict]:
    """Full OpenAI-style message list, prior turns + the new one."""
    return get_history(session_id) + [{"role": "user", "content": new_user_message}]


def as_transcript(session_id: str, max_chars: int = 4000) -> str:
    """
    Flat text transcript, for backends (the omegatech proxies) that only take
    a single text field and have no native multi-turn support of their own.
    """
    lines = []
    for m in get_history(session_id):
        prefix = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{prefix}: {m['content']}")
    text = "\n".join(lines)
    return text[-max_chars:] if len(text) > max_chars else text


def clear(session_id: str) -> None:
    _STORE.pop(session_id, None)
