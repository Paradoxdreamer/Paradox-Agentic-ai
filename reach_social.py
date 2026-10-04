"""
Tier-1 social channels for Paradox Reach (cookie-optional).

Twitter/X:
  - Single tweet: FxTwitter public API (no cookie) → optional cookie session
  - Search: requires vault twitter auth_token + ct0

Reddit:
  - Thread / listing JSON via www/old reddit (.json)
  - Cookie from vault improves success on blocked networks
"""
from __future__ import annotations

import re
from typing import Any, Optional
from urllib.parse import quote_plus, urlparse

import requests

import config
import vault

_UA = "ParadoxAI-Reach/1.0 (+https://github.com/Paradoxdreamer/Paradox-Agentic-ai)"
_TWEET_ID_RE = re.compile(
    r"(?:twitter\.com|x\.com)/(?:#!/)?(?:\w+)/status(?:es)?/(\d+)",
    re.I,
)
_TWEET_ID_BARE = re.compile(r"^\d{1,25}$")


class SocialError(RuntimeError):
    pass


def _session(extra_headers: Optional[dict] = None, cookies: Optional[dict] = None) -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": _UA, "Accept": "application/json, text/plain, */*"})
    if extra_headers:
        s.headers.update(extra_headers)
    if cookies:
        s.cookies.update(cookies)
    return s


def twitter_id(url_or_id: str) -> Optional[str]:
    s = (url_or_id or "").strip()
    if _TWEET_ID_BARE.match(s):
        return s
    m = _TWEET_ID_RE.search(s)
    return m.group(1) if m else None


def read_twitter(url_or_id: str) -> dict[str, Any]:
    tid = twitter_id(url_or_id)
    if not tid:
        raise SocialError("not a Twitter/X status URL or tweet id")

    try:
        r = _session().get(
            f"https://api.fxtwitter.com/status/{tid}",
            timeout=config.REQUEST_TIMEOUT,
        )
        if r.status_code == 200:
            data = r.json()
            tweet = data.get("tweet") or data
            if tweet and (tweet.get("text") or tweet.get("id")):
                author = tweet.get("author") or {}
                return {
                    "id": str(tweet.get("id") or tid),
                    "url": tweet.get("url") or f"https://x.com/i/status/{tid}",
                    "text": tweet.get("text") or tweet.get("content") or "",
                    "author": author.get("screen_name") or author.get("name") or tweet.get("author"),
                    "likes": tweet.get("likes") or tweet.get("like_count"),
                    "retweets": tweet.get("retweets") or tweet.get("retweet_count"),
                    "created_at": tweet.get("created_at") or tweet.get("date"),
                    "backend": "fxtwitter",
                    "content_type": "text",
                }
    except (requests.RequestException, ValueError, TypeError):
        pass

    cookies = vault.twitter_cookies()
    if cookies:
        try:
            headers = {
                "x-csrf-token": cookies["ct0"],
                "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
                "Cookie": f"auth_token={cookies['auth_token']}; ct0={cookies['ct0']}",
            }
            r = _session(headers).get(
                f"https://cdn.syndication.twimg.com/tweet-result?id={tid}&lang=en&token=0",
                timeout=config.REQUEST_TIMEOUT,
            )
            if r.status_code == 200:
                tw = r.json()
                text = tw.get("text") or tw.get("full_text") or ""
                user = tw.get("user") or {}
                return {
                    "id": str(tw.get("id_str") or tid),
                    "url": f"https://x.com/i/status/{tid}",
                    "text": text,
                    "author": user.get("screen_name") or user.get("name"),
                    "created_at": tw.get("created_at"),
                    "backend": "syndication+cookie",
                    "content_type": "text",
                }
        except (requests.RequestException, ValueError, TypeError) as e:
            raise SocialError(f"twitter cookie read failed: {e}") from e

    raise SocialError(
        f"could not read tweet {tid} (fxtwitter miss; set vault twitter cookies for fallback)"
    )


def search_twitter(query: str, limit: int = 10) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise SocialError("empty query")
    cookies = vault.twitter_cookies()
    if not cookies:
        raise SocialError(
            "twitter search needs vault cookies: owner sets auth_token + ct0 "
            "(DevTools → Application → Cookies → x.com)"
        )

    headers = {
        "x-csrf-token": cookies["ct0"],
        "authorization": "Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA",
        "Cookie": f"auth_token={cookies['auth_token']}; ct0={cookies['ct0']}",
        "x-twitter-auth-type": "OAuth2Session",
        "x-twitter-active-user": "yes",
    }
    try:
        r = _session(headers).get(
            "https://x.com/i/api/2/search/adaptive.json",
            params={
                "q": q,
                "count": max(1, min(limit, 20)),
                "result_filter": "live",
                "query_source": "typed_query",
                "pc": "1",
                "spelling_corrections": "1",
            },
            timeout=config.REQUEST_TIMEOUT,
        )
        if r.status_code in (401, 403):
            raise SocialError("twitter search unauthorized — refresh auth_token/ct0 in vault")
        r.raise_for_status()
        data = r.json()
    except SocialError:
        raise
    except requests.RequestException as e:
        raise SocialError(f"twitter search failed: {e}") from e
    except ValueError as e:
        raise SocialError(f"twitter search bad json: {e}") from e

    items: list[dict] = []
    tweets = (data.get("globalObjects") or {}).get("tweets") or {}
    users = (data.get("globalObjects") or {}).get("users") or {}
    for tid, tw in list(tweets.items())[: max(1, min(limit, 20))]:
        uid = str(tw.get("user_id_str") or tw.get("user_id") or "")
        user = users.get(uid) or {}
        items.append({
            "id": str(tid),
            "text": tw.get("full_text") or tw.get("text") or "",
            "author": user.get("screen_name"),
            "url": f"https://x.com/{user.get('screen_name', 'i')}/status/{tid}",
            "created_at": tw.get("created_at"),
        })
    return {
        "query": q,
        "count": len(items),
        "items": items,
        "backend": "x-adaptive+cookie",
    }


def _reddit_json_url(url: str) -> str:
    u = (url or "").strip()
    if not u.startswith("http"):
        if u.startswith("/"):
            u = "https://www.reddit.com" + u
        elif u.startswith("r/"):
            u = "https://www.reddit.com/" + u
        else:
            u = "https://www.reddit.com/" + u.lstrip("/")
    parsed = urlparse(u)
    path = parsed.path.rstrip("/")
    if not path.endswith(".json"):
        path = path + ".json"
    return f"https://www.reddit.com{path}" + (f"?{parsed.query}" if parsed.query else "")


def read_reddit(url: str, limit: int = 15) -> dict[str, Any]:
    target = (url or "").strip()
    if not target:
        raise SocialError("empty reddit target")

    json_url = _reddit_json_url(target)
    headers = {"User-Agent": _UA}
    cookie = vault.reddit_cookie_header()
    if cookie:
        headers["Cookie"] = cookie

    try:
        r = _session(headers).get(json_url, timeout=config.REQUEST_TIMEOUT, allow_redirects=True)
        if r.status_code in (401, 403):
            raise SocialError(
                "reddit blocked this request (403). Set vault reddit cookie from a logged-in browser."
            )
        r.raise_for_status()
        data = r.json()
    except SocialError:
        raise
    except requests.RequestException as e:
        raise SocialError(f"reddit fetch failed: {e}") from e
    except ValueError as e:
        raise SocialError(f"reddit not json: {e}") from e

    if isinstance(data, list) and data:
        post_listing = data[0].get("data", {}).get("children") or []
        post = (post_listing[0].get("data") if post_listing else {}) or {}
        comments: list[dict] = []
        if len(data) > 1:
            for child in (data[1].get("data", {}).get("children") or [])[:limit]:
                if child.get("kind") != "t1":
                    continue
                c = child.get("data") or {}
                comments.append({
                    "author": c.get("author"),
                    "body": (c.get("body") or "")[:2000],
                    "score": c.get("score"),
                })
        return {
            "kind": "post",
            "title": post.get("title"),
            "author": post.get("author"),
            "subreddit": post.get("subreddit"),
            "url": "https://www.reddit.com" + (post.get("permalink") or ""),
            "selftext": (post.get("selftext") or "")[:8000],
            "score": post.get("score"),
            "comments": comments,
            "backend": "reddit.json" + ("+cookie" if cookie else ""),
            "content_type": "text",
        }

    if isinstance(data, dict):
        children = (data.get("data") or {}).get("children") or []
        items = []
        for ch in children[:limit]:
            d = ch.get("data") or {}
            items.append({
                "title": d.get("title"),
                "author": d.get("author"),
                "subreddit": d.get("subreddit"),
                "url": "https://www.reddit.com" + (d.get("permalink") or ""),
                "score": d.get("score"),
                "num_comments": d.get("num_comments"),
            })
        return {
            "kind": "listing",
            "count": len(items),
            "items": items,
            "backend": "reddit.json" + ("+cookie" if cookie else ""),
        }

    raise SocialError("unexpected reddit response shape")


def search_reddit(query: str, limit: int = 10) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        raise SocialError("empty query")
    url = f"https://www.reddit.com/search.json?q={quote_plus(q)}&limit={max(1, min(limit, 25))}"
    return read_reddit(url, limit=limit)
