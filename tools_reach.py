"""
Reach tools for the chat agent loop.

OpenAI-style function schemas + dispatch into reach / reach_social.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import config

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "reach_read",
            "description": (
                "Read a public URL, GitHub repo, YouTube video captions, RSS feed, "
                "V2EX topic, Twitter/X status, or Reddit post. Auto-detects the source."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "URL, owner/repo, tweet id, reddit path, or V2EX target (hot/latest/t/ID)",
                    },
                    "max_chars": {
                        "type": "integer",
                        "description": "Max characters of body text to return (default 12000)",
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_search",
            "description": "Search the public web (DuckDuckGo HTML) for recent pages matching a query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer", "description": "Max results (1-10)"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_github_search",
            "description": "Search public GitHub repositories by keyword.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_v2ex",
            "description": "V2EX: hot/latest topics, node:NAME, t/TOPIC_ID, or member:USERNAME.",
            "parameters": {
                "type": "object",
                "properties": {
                    "target": {
                        "type": "string",
                        "description": "hot | latest | node:python | t/123456 | member:Livid",
                    },
                    "limit": {"type": "integer"},
                },
                "required": ["target"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_twitter",
            "description": (
                "Read a public tweet by URL or id (FxTwitter, no cookie). "
                "Keyword search needs owner vault cookies."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Tweet URL or numeric id"},
                    "query": {"type": "string", "description": "Search query (needs vault)"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_reddit",
            "description": "Read a Reddit post/listing URL or search Reddit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "reddit.com URL or r/subreddit"},
                    "query": {"type": "string", "description": "Search query"},
                    "limit": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reach_doctor",
            "description": "Report which internet Reach channels are enabled and healthy.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_HINT = (
    "You are Paradox, an agentic assistant with live internet tools. "
    "When the user asks about current facts, URLs, videos, GitHub, Twitter, Reddit, or V2EX, "
    "call the appropriate reach_* tool before answering. "
    "Summarize tool results clearly; do not invent URLs or quotes."
)


def _compact(data: Any, max_chars: int = 12000) -> str:
    try:
        text = json.dumps(data, ensure_ascii=False, indent=2)
    except (TypeError, ValueError):
        text = str(data)
    if len(text) > max_chars:
        return text[: max_chars - 20] + "\n…[truncated]"
    return text


def run_tool(name: str, arguments: dict) -> str:
    if not getattr(config, "ENABLE_REACH", True):
        return json.dumps({"error": "reach is disabled on this server"})
    args = arguments or {}
    try:
        if name == "reach_doctor":
            import reach
            return _compact(reach.doctor(), 4000)

        if name == "reach_read":
            import reach
            url = (args.get("url") or "").strip()
            if not url:
                return json.dumps({"error": "url required"})
            max_chars = int(args.get("max_chars") or 12000)
            return _compact(reach.smart_read(url, max_chars=max(1000, min(max_chars, 40000))))

        if name == "reach_search":
            import reach
            q = (args.get("query") or "").strip()
            if not q:
                return json.dumps({"error": "query required"})
            limit = int(args.get("limit") or 8)
            return _compact(reach.web_search(q, limit=max(1, min(limit, 10))))

        if name == "reach_github_search":
            import reach
            q = (args.get("query") or "").strip()
            if not q:
                return json.dumps({"error": "query required"})
            limit = int(args.get("limit") or 8)
            return _compact(reach.search_github(q, limit=max(1, min(limit, 15))))

        if name == "reach_v2ex":
            import reach
            target = (args.get("target") or "hot").strip()
            limit = int(args.get("limit") or 15)
            return _compact(reach.read_v2ex(target, limit=max(1, min(limit, 30))))

        if name == "reach_twitter":
            import reach_social
            query = (args.get("query") or "").strip()
            url = (args.get("url") or "").strip()
            limit = int(args.get("limit") or 10)
            if query:
                return _compact(reach_social.search_twitter(query, limit=max(1, min(limit, 15))))
            if url:
                return _compact(reach_social.read_twitter(url))
            return json.dumps({"error": "provide url or query"})

        if name == "reach_reddit":
            import reach_social
            query = (args.get("query") or "").strip()
            url = (args.get("url") or "").strip()
            limit = int(args.get("limit") or 10)
            if query:
                return _compact(reach_social.search_reddit(query, limit=max(1, min(limit, 20))))
            if url:
                return _compact(reach_social.read_reddit(url, limit=max(1, min(limit, 20))))
            return json.dumps({"error": "provide url or query"})

        return json.dumps({"error": f"unknown tool '{name}'"})
    except Exception as e:
        return json.dumps({"error": str(e)})


def parse_tool_arguments(raw: Any) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {"_raw": raw}
    return {}
