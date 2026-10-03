"""Reach HTTP routes — registered onto the FastAPI app."""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

import auth
import browser
import config
import ratelimit
import reach


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


def _require_reach_enabled():
    if not getattr(config, "ENABLE_REACH", True):
        raise HTTPException(403, "reach is disabled. Set PARADOX_ENABLE_REACH=1 on the server if you want it.")


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
        except (reach.ReachError, browser.BrowserError) as e:
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
