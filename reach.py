"""
Paradox Reach — internet eyes for the agent.

Inspired by Agent-Reach (MIT, Panniantong/Agent-Reach): multi-backend
routing, zero-config public channels, doctor/status. Implemented natively
so Fly/Docker don't need shell CLIs (yt-dlp, gh, opencli).

Channels (tier 0, public HTTP only):
  web      Jina Reader → local HTML extract (SSRF-safe)
  rss      RSS / Atom feeds
  youtube  captions via YouTube timedtext
  github   public REST API (repo, readme, issues, search)
  search   DuckDuckGo HTML (no key)
  v2ex     public JSON API (hot / topic / node / member)
  read     smart router: pick channel from URL, else web
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from html import unescape
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

import requests
from bs4 import BeautifulSoup

import browser
import config

_assert_public_url = browser._assert_public_url
BrowserError = browser.BrowserError


class ReachError(RuntimeError):
    pass


_UA = "ParadoxAI-Reach/1.0 (+https://github.com/Paradoxdreamer/Paradox-Agentic-ai)"
_JINA = "https://r.jina.ai/"
_MAX_TEXT = 24_000
_YT_ID_RE = re.compile(
    r"(?:youtube\.com/(?:watch\?v=|embed/|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})"
)
_GH_RE = re.compile(r"github\.com/([^/\s]+)/([^/\s?#]+)")
_V2EX_TOPIC_RE = re.compile(r"v2ex\.com/t/(\d+)", re.I)
_V2EX_MEMBER_RE = re.compile(r"v2ex\.com/member/([A-Za-z0-9_-]+)", re.I)
_V2EX_NODE_RE = re.compile(r"v2ex\.com/go/([A-Za-z0-9_-]+)", re.I)


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "*/*"})
    return s


def _trim(text: str, limit: int = _MAX_TEXT) -> tuple[str, bool]:
    text = (text or "").strip()
    if len(text) <= limit:
        return text, False
    return text[:limit], True


def doctor() -> dict[str, Any]:
    """Capability report (Agent-Reach style)."""
    channels = {
        "web": {
            "tier": 0,
            "backends": ["jina", "local"],
            "status": "ok",
            "message": "Jina Reader + local HTML extract",
        },
        "rss": {
            "tier": 0,
            "backends": ["stdlib-xml"],
            "status": "ok",
            "message": "RSS/Atom via stdlib",
        },
        "youtube": {
            "tier": 0,
            "backends": ["timedtext"],
            "status": "ok",
            "message": "YouTube captions (public timedtext)",
        },
        "github": {
            "tier": 0,
            "backends": ["api.github.com"],
            "status": "ok",
            "message": "Public GitHub REST (unauthenticated rate limits apply)",
        },
        "search": {
            "tier": 0,
            "backends": ["duckduckgo-html"],
            "status": "ok",
            "message": "DuckDuckGo HTML search (no API key)",
        },
        "v2ex": {
            "tier": 0,
            "backends": ["api.v2ex.com"],
            "status": "ok",
            "message": "V2EX public JSON (hot / topic / node / member)",
        },
    }
    enabled = bool(getattr(config, "ENABLE_REACH", True))
    return {
        "enabled": enabled,
        "inspired_by": "https://github.com/Panniantong/Agent-Reach",
        "channels": channels,
        "ok_count": sum(1 for c in channels.values() if c["status"] == "ok"),
        "total": len(channels),
    }
