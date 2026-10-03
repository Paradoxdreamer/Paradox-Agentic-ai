from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Optional

from fastapi import Cookie, Depends, FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import accounts
import auth
import browser
import config
import consensus
import credits
import executor
import owner
import pipeline
import providers
import ratelimit
import reach
import router
import sessions
import snapshots
import workspace

app = FastAPI(title=config.APP_NAME)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Owner-Key"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
        "font-src https://fonts.gstatic.com; img-src 'self' data:; connect-src *; frame-ancestors 'none'"
    )
    return response

STATIC_DIR = Path(__file__).parent / "static"
SESSION_MARK = "@@SESSION@@"
ROUTED_MARK = "@@ROUTED@@"

def _skey(user: str, session_id: str) -> str:
    return f"{user}:{session_id}"

def _valid_agent(agent: str) -> bool:
    return agent in ("auto", "consensus") or agent in providers.list_provider_ids()

def _require_accounts_mode():
    if config.AUTH_MODE != "accounts":
        raise HTTPException(404, "accounts mode isn't enabled (set PARADOX_AUTH_MODE=accounts)")

def _require_owner(user: str, x_owner_key: str | None = None):
    if not owner.is_owner(user, x_owner_key):
        raise HTTPException(403, owner.owner_setup_hint())

def _require_exec_enabled():
    if not config.ENABLE_EXEC:
        raise HTTPException(403, "command execution is disabled. Set PARADOX_ENABLE_EXEC=1 on the server if you want it.")

def _require_browse_enabled():
    if not config.ENABLE_BROWSE:
        raise HTTPException(403, "browsing is disabled. Set PARADOX_ENABLE_BROWSE=1 on the server if you want it.")

def _require_reach_enabled():
    if not getattr(config, "ENABLE_REACH", True):
        raise HTTPException(403, "reach is disabled. Set PARADOX_ENABLE_REACH=1 on the server if you want it.")

def _charge_or_402(user: str, amount: int, kind: str):
    try:
        credits.check_and_charge(user, amount, kind)
    except credits.InsufficientCreditsError as e:
        raise HTTPException(402, str(e)) from e
