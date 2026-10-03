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
import reach_v2ex

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


# Load remaining channel implementations from the pre-split body if present;
# otherwise the functions below are the full implementations.

def read_web(url: str, max_chars: int = _MAX_TEXT) -> dict:
    """Read a page: try Jina (clean markdown), fall back to local extract."""
    _assert_public_url(url)
    errors: list[str] = []
    try:
        r = _session().get(
            _JINA + url,
            timeout=min(45, config.REQUEST_TIMEOUT + 15),
            headers={"Accept": "text/plain"},
        )
        if r.status_code == 200 and r.text.strip():
            sample = r.text[:4000].casefold()
            antibot = (
                ("warning:" in sample and "requiring captcha" in sample)
                or "title: just a moment..." in sample
                or "title: attention required! | cloudflare" in sample
            )
            if not antibot:
                text, trunc = _trim(r.text, max_chars)
                return {
                    "url": url,
                    "title": _title_from_jina(r.text) or url,
                    "text": text,
                    "truncated": trunc,
                    "backend": "jina",
                    "content_type": "markdown",
                }
            errors.append("jina: antibot challenge page")
        else:
            errors.append(f"jina: HTTP {r.status_code}")
    except requests.RequestException as e:
        errors.append(f"jina: {e}")
    try:
        local = browser.fetch(url, max_chars=max_chars)
        local["backend"] = "local"
        local["content_type"] = "text"
        local["errors"] = errors
        return local
    except BrowserError as e:
        errors.append(f"local: {e}")
        raise ReachError("; ".join(errors)) from e


def _title_from_jina(md: str) -> str:
    for line in md.splitlines()[:30]:
        line = line.strip()
        if line.lower().startswith("title:"):
            return line.split(":", 1)[1].strip()
        if line.startswith("# "):
            return line[2:].strip()
    return ""


_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def read_rss(url: str, limit: int = 15) -> dict:
    _assert_public_url(url)
    try:
        r = _session().get(url, timeout=config.REQUEST_TIMEOUT)
        r.raise_for_status()
    except requests.RequestException as e:
        raise ReachError(f"rss fetch failed: {e}") from e
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise ReachError(f"not a valid feed: {e}") from e
    tag = root.tag.lower()
    items: list[dict] = []
    feed_title = ""
    if tag.endswith("rss") or "rss" in tag:
        channel = root.find("channel")
        if channel is not None:
            feed_title = (channel.findtext("title") or "").strip()
            for item in channel.findall("item")[:limit]:
                items.append({
                    "title": (item.findtext("title") or "").strip(),
                    "link": (item.findtext("link") or "").strip(),
                    "published": (item.findtext("pubDate") or "").strip(),
                    "summary": _strip_html(item.findtext("description") or "")[:500],
                })
    else:
        feed_title = (root.findtext("a:title", default="", namespaces=_ATOM_NS) or root.findtext("title") or "").strip()
        entries = root.findall("a:entry", _ATOM_NS) or root.findall("entry")
        for entry in entries[:limit]:
            title = (entry.findtext("a:title", default="", namespaces=_ATOM_NS) or entry.findtext("title") or "").strip()
            link_el = entry.find("a:link", _ATOM_NS) or entry.find("link")
            href = ""
            if link_el is not None:
                href = link_el.get("href") or (link_el.text or "")
            summary = (
                entry.findtext("a:summary", default="", namespaces=_ATOM_NS)
                or entry.findtext("summary")
                or entry.findtext("a:content", default="", namespaces=_ATOM_NS)
                or entry.findtext("content")
                or ""
            )
            published = (
                entry.findtext("a:updated", default="", namespaces=_ATOM_NS)
                or entry.findtext("updated")
                or entry.findtext("a:published", default="", namespaces=_ATOM_NS)
                or entry.findtext("published")
                or ""
            )
            items.append({
                "title": title,
                "link": href.strip(),
                "published": published.strip(),
                "summary": _strip_html(summary)[:500],
            })
    return {
        "url": url,
        "title": feed_title or url,
        "items": items,
        "count": len(items),
        "backend": "stdlib-xml",
    }


def _strip_html(s: str) -> str:
    s = unescape(s or "")
    return re.sub(r"<[^>]+>", " ", s)


def youtube_id(url_or_id: str) -> Optional[str]:
    s = (url_or_id or "").strip()
    if re.fullmatch(r"[A-Za-z0-9_-]{11}", s):
        return s
    m = _YT_ID_RE.search(s)
    return m.group(1) if m else None


def read_youtube(url_or_id: str, lang: str = "en") -> dict:
    vid = youtube_id(url_or_id)
    if not vid:
        raise ReachError("not a YouTube URL or video id")
    list_url = f"https://www.youtube.com/api/timedtext?type=list&v={vid}"
    try:
        lr = _session().get(list_url, timeout=config.REQUEST_TIMEOUT)
        lr.raise_for_status()
    except requests.RequestException as e:
        raise ReachError(f"youtube track list failed: {e}") from e
    langs: list[str] = []
    try:
        root = ET.fromstring(lr.content)
        for track in root.findall("track"):
            code = track.get("lang_code") or ""
            if code:
                langs.append(code)
    except ET.ParseError:
        pass
    preferred = [lang, "en", "en-US", "en-GB", "a." + lang]
    pick = None
    for cand in preferred:
        if cand in langs:
            pick = cand
            break
    if not pick and langs:
        pick = langs[0]
    if not pick:
        raise ReachError(f"no captions for video {vid} (available: {', '.join(langs) or 'none'})")
    cap_url = f"https://www.youtube.com/api/timedtext?v={vid}&lang={pick}"
    try:
        cr = _session().get(cap_url, timeout=config.REQUEST_TIMEOUT)
        cr.raise_for_status()
    except requests.RequestException as e:
        raise ReachError(f"youtube captions failed: {e}") from e
    lines: list[str] = []
    try:
        root = ET.fromstring(cr.content)
        for p in root.findall("text"):
            t = unescape((p.text or "").replace("\n", " ")).strip()
            if t:
                lines.append(t)
    except ET.ParseError as e:
        raise ReachError(f"caption parse failed: {e}") from e
    text, trunc = _trim("\n".join(lines))
    return {
        "url": f"https://www.youtube.com/watch?v={vid}",
        "video_id": vid,
        "lang": pick,
        "languages": langs,
        "text": text,
        "truncated": trunc,
        "backend": "timedtext",
        "content_type": "transcript",
    }


def _gh_headers() -> dict:
    h = {"Accept": "application/vnd.github+json", "User-Agent": _UA}
    token = getattr(config, "GITHUB_TOKEN", "") or ""
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def read_github(url_or_slug: str) -> dict:
    owner = repo = None
    s = (url_or_slug or "").strip().rstrip("/")
    m = _GH_RE.search(s)
    if m:
        owner, repo = m.group(1), m.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
    elif "/" in s and " " not in s:
        parts = s.split("/")
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1]
    if not owner or not repo:
        raise ReachError("expected github.com/owner/repo or owner/repo")
    base = f"https://api.github.com/repos/{owner}/{repo}"
    try:
        r = _session().get(base, headers=_gh_headers(), timeout=config.REQUEST_TIMEOUT)
        if r.status_code == 404:
            raise ReachError(f"repo not found: {owner}/{repo}")
        r.raise_for_status()
        meta = r.json()
    except ReachError:
        raise
    except requests.RequestException as e:
        raise ReachError(f"github api failed: {e}") from e
    readme_text = ""
    try:
        rr = _session().get(
            base + "/readme",
            headers={**_gh_headers(), "Accept": "application/vnd.github.raw"},
            timeout=config.REQUEST_TIMEOUT,
        )
        if rr.status_code == 200:
            readme_text, _ = _trim(rr.text, 12_000)
    except requests.RequestException:
        pass
    return {
        "url": meta.get("html_url") or f"https://github.com/{owner}/{repo}",
        "full_name": meta.get("full_name"),
        "description": meta.get("description") or "",
        "stars": meta.get("stargazers_count"),
        "forks": meta.get("forks_count"),
        "language": meta.get("language"),
        "topics": meta.get("topics") or [],
        "default_branch": meta.get("default_branch"),
        "updated_at": meta.get("updated_at"),
        "readme": readme_text,
        "backend": "api.github.com",
    }


def search_github(query: str, limit: int = 8) -> dict:
    q = (query or "").strip()
    if not q:
        raise ReachError("empty query")
    try:
        r = _session().get(
            "https://api.github.com/search/repositories",
            params={"q": q, "sort": "stars", "order": "desc", "per_page": min(limit, 20)},
            headers=_gh_headers(),
            timeout=config.REQUEST_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
    except requests.RequestException as e:
        raise ReachError(f"github search failed: {e}") from e
    items = []
    for it in data.get("items") or []:
        items.append({
            "full_name": it.get("full_name"),
            "url": it.get("html_url"),
            "description": it.get("description") or "",
            "stars": it.get("stargazers_count"),
            "language": it.get("language"),
        })
    return {"query": q, "count": len(items), "items": items, "backend": "api.github.com"}


def web_search(query: str, limit: int = 8) -> dict:
    q = (query or "").strip()
    if not q:
        raise ReachError("empty query")
    try:
        r = _session().post(
            "https://html.duckduckgo.com/html/",
            data={"q": q},
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": _UA, "Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise ReachError(f"search failed: {e}") from e
    soup = BeautifulSoup(r.text, "html.parser")
    results = []
    for res in soup.select(".result")[:limit]:
        a = res.select_one("a.result__a")
        snippet_el = res.select_one(".result__snippet")
        if not a:
            continue
        href = a.get("href") or ""
        if "uddg=" in href:
            from urllib.parse import unquote
            qs = parse_qs(urlparse(href).query)
            href = unquote(qs.get("uddg", [href])[0])
        results.append({
            "title": a.get_text(" ", strip=True),
            "url": href,
            "snippet": snippet_el.get_text(" ", strip=True) if snippet_el else "",
        })
    return {"query": q, "count": len(results), "items": results, "backend": "duckduckgo-html"}


def smart_read(target: str, max_chars: int = _MAX_TEXT) -> dict:
    t = (target or "").strip()
    if not t:
        raise ReachError("empty target")
    low = t.casefold()
    if "youtube.com" in low or "youtu.be" in low or youtube_id(t):
        try:
            return read_youtube(t)
        except ReachError:
            pass
    if "github.com" in low or re.match(r"^[\w.-]+/[\w.-]+$", t):
        try:
            return read_github(t)
        except ReachError:
            pass
    if "v2ex.com" in low or t.casefold() in ("hot", "v2ex", "v2ex/hot"):
        try:
            return reach_v2ex.read_v2ex(t)
        except Exception:
            pass
    if any(x in low for x in (".xml", "/feed", "/rss", "atom", "feeds/")):
        try:
            return read_rss(t)
        except ReachError:
            pass
    return read_web(t, max_chars=max_chars)


read_v2ex = reach_v2ex.read_v2ex
_V2EX_TOPIC_RE = reach_v2ex._V2EX_TOPIC_RE
_V2EX_MEMBER_RE = reach_v2ex._V2EX_MEMBER_RE
_V2EX_NODE_RE = reach_v2ex._V2EX_NODE_RE
