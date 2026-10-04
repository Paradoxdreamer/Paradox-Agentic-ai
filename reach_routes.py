"""Reach HTTP routes — registered onto the FastAPI app."""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from pydantic import BaseModel

import auth
import browser
import config
import owner
import ratelimit
import reach
import reach_social
import vault


class ReachReadRequest(BaseModel):
    url: str
    max_chars: int = 24000


class ReachSearchRequest(BaseModel):
    query: str
    limit: int = 8


class ReachYoutubeRequest(BaseModel):
    url: str
    lang: str = "en"


class ReachV2exRequest(BaseModel):
    target: str = "hot"
    limit: int = 15


class ReachTwitterRequest(BaseModel):
    url: str = ""
    query: str = ""
    limit: int = 10


class ReachRedditRequest(BaseModel):
    url: str = ""
    query: str = ""
    limit: int = 10


class VaultSetRequest(BaseModel):
    platform: str
    secrets: dict


def _require_reach_enabled():
    if not getattr(config, "ENABLE_REACH", True):
        raise HTTPException(403, "reach is disabled. Set PARADOX_ENABLE_REACH=1 on the server if you want it.")


def _require_owner(user: str, x_owner_key: Optional[str]):
    if not owner.is_owner(user, x_owner_key):
        raise HTTPException(403, "owner only: " + owner.owner_setup_hint())


def register(app):
    @app.get("/api/reach/doctor")
    def reach_doctor(user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        return reach.doctor()

    @app.post("/api/reach/read")
    def reach_read(req: ReachReadRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=30, window_seconds=60)
        try:
            return reach.smart_read(req.url, max_chars=max(1000, min(req.max_chars, 50000)))
        except (reach.ReachError, browser.BrowserError, reach_social.SocialError) as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/web")
    def reach_web(req: ReachReadRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=30, window_seconds=60)
        try:
            return reach.read_web(req.url, max_chars=max(1000, min(req.max_chars, 50000)))
        except (reach.ReachError, browser.BrowserError) as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/rss")
    def reach_rss(req: ReachReadRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=20, window_seconds=60)
        try:
            return reach.read_rss(req.url)
        except (reach.ReachError, browser.BrowserError) as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/youtube")
    def reach_youtube(req: ReachYoutubeRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=15, window_seconds=60)
        try:
            return reach.read_youtube(req.url, lang=req.lang or "en")
        except reach.ReachError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/github")
    def reach_github(req: ReachReadRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=20, window_seconds=60)
        try:
            return reach.read_github(req.url)
        except reach.ReachError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/search")
    def reach_search(req: ReachSearchRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=20, window_seconds=60)
        try:
            return reach.web_search(req.query, limit=max(1, min(req.limit, 15)))
        except reach.ReachError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/github-search")
    def reach_github_search(req: ReachSearchRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=15, window_seconds=60)
        try:
            return reach.search_github(req.query, limit=max(1, min(req.limit, 20)))
        except reach.ReachError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/v2ex")
    def reach_v2ex(req: ReachV2exRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=20, window_seconds=60)
        try:
            return reach.read_v2ex(req.target or "hot", limit=max(1, min(req.limit, 30)))
        except reach.ReachError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/twitter")
    def reach_twitter(req: ReachTwitterRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=15, window_seconds=60)
        try:
            if (req.query or "").strip():
                return reach_social.search_twitter(req.query, limit=max(1, min(req.limit, 20)))
            if not (req.url or "").strip():
                raise HTTPException(400, "provide url (tweet) or query (search)")
            return reach_social.read_twitter(req.url)
        except reach_social.SocialError as e:
            raise HTTPException(502, str(e)) from e

    @app.post("/api/reach/reddit")
    def reach_reddit(req: ReachRedditRequest, request: Request, user: str = Depends(auth.get_current_user)):
        _require_reach_enabled()
        ratelimit.enforce(request, "reach", limit=15, window_seconds=60)
        try:
            if (req.query or "").strip():
                return reach_social.search_reddit(req.query, limit=max(1, min(req.limit, 25)))
            if not (req.url or "").strip():
                raise HTTPException(400, "provide url (post/listing) or query (search)")
            return reach_social.read_reddit(req.url, limit=max(1, min(req.limit, 30)))
        except reach_social.SocialError as e:
            raise HTTPException(502, str(e)) from e

    @app.get("/api/vault/status")
    def vault_status(
        user: str = Depends(auth.get_current_user),
        x_owner_key: Optional[str] = Header(default=None),
    ):
        _require_owner(user, x_owner_key)
        return vault.status()

    @app.put("/api/vault/{platform}")
    def vault_set(
        platform: str,
        req: VaultSetRequest,
        user: str = Depends(auth.get_current_user),
        x_owner_key: Optional[str] = Header(default=None),
    ):
        _require_owner(user, x_owner_key)
        try:
            return vault.set_secrets(platform or req.platform, req.secrets or {})
        except ValueError as e:
            raise HTTPException(400, str(e)) from e

    @app.delete("/api/vault/{platform}")
    def vault_clear(
        platform: str,
        user: str = Depends(auth.get_current_user),
        x_owner_key: Optional[str] = Header(default=None),
    ):
        _require_owner(user, x_owner_key)
        try:
            return vault.clear_platform(platform)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
