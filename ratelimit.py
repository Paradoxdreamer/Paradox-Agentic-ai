"""
Paradox AI - ratelimit

A minimal in-memory sliding-window rate limiter, keyed by client IP. This
is process-local (resets on restart, doesn't coordinate across multiple
server processes/replicas) -- fine for a single-instance deployment, not a
substitute for a real rate-limiting layer (e.g. at a reverse proxy or
API gateway) if you scale out or face real abuse.

Used for: auth endpoints (signup/login -- brute-force/credential-stuffing
defense) and, more loosely, as a general backstop on the rest of the API.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_HITS: dict[str, deque] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    # Respect a proxy header if present (e.g. behind nginx/a load balancer),
    # falling back to the direct connection. Trusting X-Forwarded-For blindly
    # is only safe if you control the proxy in front of this -- if you don't,
    # remove this header check so a client can't spoof their way around limits.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(request: Request, key: str, limit: int, window_seconds: int) -> None:
    """Raises 429 if `key` (usually f"{route}:{ip}") has exceeded `limit` hits in the window."""
    ip = _client_ip(request)
    bucket_key = f"{key}:{ip}"
    now = time.time()
    hits = _HITS[bucket_key]
    while hits and hits[0] < now - window_seconds:
        hits.popleft()
    if len(hits) >= limit:
        raise HTTPException(429, "too many requests -- slow down and try again shortly")
    hits.append(now)
