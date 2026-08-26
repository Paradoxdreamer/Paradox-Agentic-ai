"""
Paradox AI - browser

Fetches a public http(s) URL and returns readable text.
Private, loopback, link-local, and metadata IPs are blocked (SSRF guard).
"""
from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

import config


class BrowserError(RuntimeError):
    pass


_BLOCKED_HOST_NAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.google.com",
}


def _is_bad_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise BrowserError("url must start with http:// or https://")
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise BrowserError("url is missing a host")
    if host in _BLOCKED_HOST_NAMES or host.endswith(".internal") or host.endswith(".local"):
        raise BrowserError(f"host '{host}' is not allowed")
    if parsed.username or parsed.password:
        raise BrowserError("urls with embedded credentials are not allowed")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        raise BrowserError(f"could not resolve {host}: {e}") from e
    if not infos:
        raise BrowserError(f"could not resolve {host}")
    for info in infos:
        raw = info[4][0]
        ip = ipaddress.ip_address(raw.split("%")[0])
        if _is_bad_ip(ip):
            raise BrowserError(f"host '{host}' resolves to a blocked address ({ip})")


def fetch(url: str, max_chars: int = 8000) -> dict:
    _assert_public_url(url)
    try:
        r = requests.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": "ParadoxAI/1.0 (+workspace agent)"},
            allow_redirects=True,
        )
        _assert_public_url(r.url)
        r.raise_for_status()
    except BrowserError:
        raise
    except requests.RequestException as e:
        raise BrowserError(f"could not fetch {url}: {e}") from e

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.get_text(separator=" ").split())
    truncated = text[:max_chars]
    return {"url": r.url, "title": title, "text": truncated, "truncated": len(text) > max_chars}
