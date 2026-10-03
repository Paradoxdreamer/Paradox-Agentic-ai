"""V2EX public JSON channel for Paradox Reach."""
from __future__ import annotations

import re
from typing import Any, Optional

import requests

import config

class ReachError(RuntimeError):
    pass

_UA = "ParadoxAI-Reach/1.0 (+https://github.com/Paradoxdreamer/Paradox-Agentic-ai)"
_V2EX_TOPIC_RE = re.compile(r"v2ex\.com/t/(\d+)", re.I)
_V2EX_MEMBER_RE = re.compile(r"v2ex\.com/member/([A-Za-z0-9_-]+)", re.I)
_V2EX_NODE_RE = re.compile(r"v2ex\.com/go/([A-Za-z0-9_-]+)", re.I)

def _session():
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "*/*"})
    return s

# ── V2EX (public JSON API) ──────────────────────────────────────────

def _v2ex_get(path: str, params: Optional[dict] = None) -> Any:
    url = f"https://www.v2ex.com/api/{path.lstrip('/')}"
    try:
        r = _session().get(url, params=params or {}, timeout=config.REQUEST_TIMEOUT)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise ReachError(f"v2ex request failed: {e}") from e
    except ValueError as e:
        raise ReachError(f"v2ex invalid json: {e}") from e


def _v2ex_topic_summary(t: dict) -> dict:
    node = t.get("node") or {}
    member = t.get("member") or {}
    return {
        "id": t.get("id"),
        "title": t.get("title"),
        "url": t.get("url"),
        "replies": t.get("replies"),
        "node": node.get("name") or node.get("title"),
        "author": member.get("username"),
        "created": t.get("created"),
        "content": (t.get("content") or "")[:2000] or None,
    }


def read_v2ex(target: str = "hot", limit: int = 15) -> dict:
    """Read V2EX: hot topics, a topic+replies, a node, or a member.

    target examples:
      hot | latest
      https://www.v2ex.com/t/123456
      https://www.v2ex.com/go/python
      https://www.v2ex.com/member/Livid
      node:python | member:Livid | topic:123456
    """
    t = (target or "hot").strip()
    low = t.casefold()

    if low.startswith("node:"):
        name = t.split(":", 1)[1].strip()
        node = _v2ex_get("nodes/show.json", {"name": name})
        topics = _v2ex_get("topics/show.json", {"node_name": name})
        if isinstance(topics, list):
            topics = topics[: max(1, min(limit, 30))]
        else:
            topics = []
        return {
            "kind": "node",
            "node": {
                "name": node.get("name"),
                "title": node.get("title"),
                "topics": node.get("topics"),
                "header": node.get("header"),
            },
            "items": [_v2ex_topic_summary(x) for x in topics if isinstance(x, dict)],
            "backend": "api.v2ex.com",
        }

    if low.startswith("member:"):
        username = t.split(":", 1)[1].strip()
        member = _v2ex_get("members/show.json", {"username": username})
        return {
            "kind": "member",
            "member": {
                "username": member.get("username"),
                "id": member.get("id"),
                "url": member.get("url"),
                "bio": member.get("bio"),
                "created": member.get("created"),
            },
            "backend": "api.v2ex.com",
        }

    if low.startswith("topic:"):
        tid = t.split(":", 1)[1].strip()
        return _v2ex_topic_detail(tid)

    m = _V2EX_TOPIC_RE.search(t)
    if m:
        return _v2ex_topic_detail(m.group(1))

    m = _V2EX_MEMBER_RE.search(t)
    if m:
        return read_v2ex(f"member:{m.group(1)}")

    m = _V2EX_NODE_RE.search(t)
    if m:
        return read_v2ex(f"node:{m.group(1)}", limit=limit)

    if low in ("", "hot", "v2ex", "v2ex/hot"):
        path = "topics/hot.json"
        kind = "hot"
    elif low in ("latest", "v2ex/latest"):
        path = "topics/latest.json"
        kind = "latest"
    else:
        return read_v2ex(f"node:{t}", limit=limit)

    data = _v2ex_get(path)
    if not isinstance(data, list):
        raise ReachError("v2ex unexpected response")
    items = [_v2ex_topic_summary(x) for x in data[: max(1, min(limit, 30))] if isinstance(x, dict)]
    return {"kind": kind, "count": len(items), "items": items, "backend": "api.v2ex.com"}


def _v2ex_topic_detail(topic_id: str) -> dict:
    topics = _v2ex_get("topics/show.json", {"id": topic_id})
    if not isinstance(topics, list) or not topics:
        raise ReachError(f"v2ex topic {topic_id} not found")
    topic = topics[0]
    replies: list[dict] = []
    try:
        raw = _v2ex_get("replies/show.json", {"topic_id": topic_id})
        if isinstance(raw, list):
            for r in raw[:50]:
                if not isinstance(r, dict):
                    continue
                member = r.get("member") or {}
                replies.append({
                    "id": r.get("id"),
                    "author": member.get("username"),
                    "content": (r.get("content") or "")[:1500],
                    "created": r.get("created"),
                })
    except ReachError:
        pass
    summary = _v2ex_topic_summary(topic)
    summary["content"] = topic.get("content") or topic.get("content_rendered") or ""
    return {
        "kind": "topic",
        "topic": summary,
        "replies": replies,
        "reply_count": len(replies),
        "backend": "api.v2ex.com",
    }
