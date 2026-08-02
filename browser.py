"""
Paradox AI - browser

A minimal "browse the web" tool: fetches a URL and returns readable text
(title + stripped body copy) so an agent's context isn't blown out by raw HTML.
"""
from __future__ import annotations

import requests
from bs4 import BeautifulSoup

import config


class BrowserError(RuntimeError):
    pass


def fetch(url: str, max_chars: int = 8000) -> dict:
    if not (url.startswith("http://") or url.startswith("https://")):
        raise BrowserError("url must start with http:// or https://")

    try:
        r = requests.get(
            url,
            timeout=config.REQUEST_TIMEOUT,
            headers={"User-Agent": "ParadoxAI/1.0 (+workspace agent)"},
        )
        r.raise_for_status()
    except requests.RequestException as e:
        raise BrowserError(f"could not fetch {url}: {e}") from e

    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.string.strip() if soup.title and soup.title.string else url

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    text = " ".join(soup.get_text(separator=" ").split())
    truncated = text[:max_chars]

    return {"url": url, "title": title, "text": truncated, "truncated": len(text) > max_chars}
