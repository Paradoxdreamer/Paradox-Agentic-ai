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

def _charge_or_402(user: str, amount: int, kind: str):
    try:
        credits.check_and_charge(user, amount, kind)
    except credits.InsufficientCreditsError as e:
        raise HTTPException(402, str(e)) from e

class ChatRequest(BaseModel):
    agent: str
    message: str
    session_id: Optional[str] = None
    image_b64: Optional[str] = None

class ConsensusRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider_ids: Optional[list[str]] = None

class FileWriteRequest(BaseModel):
    path: str
    content: str

class BrowseRequest(BaseModel):
    url: str

class PipelineRequest(BaseModel):
    task: str
    write_files: bool = True
    role_providers: Optional[dict[str, str]] = None

class SnapshotRequest(BaseModel):
    label: Optional[str] = None

class ExecuteRequest(BaseModel):
    command: str
    timeout: int = 20

class AutoFixRequest(BaseModel):
    command: str
    file_path: Optional[str] = None
    max_attempts: int = 3
    timeout: int = 20
    coder_provider_id: str = "claude"

class ProviderCreateRequest(BaseModel):
    id: str
    name: Optional[str] = None
    description: Optional[str] = None
    kind: str
    base_url: str
    path: Optional[str] = None
    message_param: Optional[str] = None
    session_param: Optional[str] = None
    image_param: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    api_key_env: Optional[str] = None
    api_key_header: Optional[str] = None
    api_key_param: Optional[str] = None
    platform: Optional[str] = None
    supports_streaming: Optional[bool] = None
    supports_images: Optional[bool] = None
    max_retries: int = 2
    timeout: int = 60

class SignupRequest(BaseModel):
    email: str
    password: str
    accepted_terms: bool = False

class LoginRequest(BaseModel):
    email: str
    password: str

@app.get("/api/meta")
def meta():
    return {
        "name": config.APP_NAME,
        "tagline": config.APP_TAGLINE,
        "multi_tenant": auth.MULTI_TENANT,
        "auth_mode": config.AUTH_MODE,
        "google_login_available": bool(config.GOOGLE_CLIENT_ID),
        "owner_key_configured": bool(config.OWNER_KEY),
        "exec_enabled": config.ENABLE_EXEC,
        "browse_enabled": config.ENABLE_BROWSE,
        "owner_hint": owner.owner_setup_hint(),
    }

@app.get("/terms")
def terms():
    return PlainTextResponse((Path(__file__).parent / "TERMS_OF_SERVICE.md").read_text(), media_type="text/plain; charset=utf-8")

@app.get("/privacy")
def privacy():
    return PlainTextResponse((Path(__file__).parent / "PRIVACY_POLICY.md").read_text(), media_type="text/plain; charset=utf-8")

@app.post("/api/auth/signup")
def signup(req: SignupRequest, request: Request):
    _require_accounts_mode()
    ratelimit.enforce(request, "signup", limit=5, window_seconds=300)
    try:
        user = accounts.signup_email(req.email, req.password, req.accepted_terms)
    except accounts.AccountError as e:
        raise HTTPException(400, str(e)) from e
    return accounts.public_view(user)

@app.post("/api/auth/login")
def login(req: LoginRequest, request: Request):
    _require_accounts_mode()
    ratelimit.enforce(request, "login", limit=10, window_seconds=300)
    try:
        user = accounts.login_email(req.email, req.password)
    except accounts.AccountError as e:
        raise HTTPException(401, str(e)) from e
    return accounts.public_view(user)

@app.get("/api/auth/me")
def me(user: str = Depends(auth.get_current_user)):
    _require_accounts_mode()
    import db
    u = db.get_user(user)
    if not u:
        raise HTTPException(404, "user not found")
    return accounts.public_view(u)

@app.post("/api/auth/rotate-key")
def rotate_key_route(user: str = Depends(auth.get_current_user)):
    _require_accounts_mode()
    return {"api_key": accounts.rotate_key(user)}

@app.get("/auth/google/login")
def google_login():
    _require_accounts_mode()
    state = accounts.make_oauth_state()
    redirect_uri = config.GOOGLE_REDIRECT_BASE.rstrip("/") + "/auth/google/callback"
    try:
        url = accounts.google_login_url(redirect_uri, state)
    except accounts.AccountError as e:
        raise HTTPException(400, str(e)) from e
    resp = RedirectResponse(url)
    resp.set_cookie("paradox_oauth_state", state, max_age=600, httponly=True, samesite="lax", secure=config.GOOGLE_REDIRECT_BASE.startswith("https://"))
    return resp

@app.get("/auth/google/callback")
def google_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None, paradox_oauth_state: Optional[str] = Cookie(default=None)):
    _require_accounts_mode()
    if error:
        return RedirectResponse(f"/?login_error={error}")
    if not code:
        return RedirectResponse("/?login_error=missing_code")
    if not accounts.check_oauth_state(state) or not paradox_oauth_state or paradox_oauth_state != state:
        return RedirectResponse("/?login_error=bad_oauth_state")
    redirect_uri = config.GOOGLE_REDIRECT_BASE.rstrip("/") + "/auth/google/callback"
    try:
        user = accounts.google_callback(code, redirect_uri)
    except accounts.AccountError as e:
        return RedirectResponse(f"/?login_error={str(e)[:120]}")
    resp = RedirectResponse("/#login_token=" + user["api_key"])
    resp.delete_cookie("paradox_oauth_state")
    return resp

@app.get("/api/owner-status")
def owner_status(user: str = Depends(auth.get_current_user), x_owner_key: Optional[str] = Header(default=None)):
    return {"is_owner": owner.is_owner(user, x_owner_key), "hint": owner.owner_setup_hint(), "owner_key_configured": bool(config.OWNER_KEY)}

@app.get("/api/providers")
def list_providers(user: str = Depends(auth.get_current_user)):
    return {"providers": [providers.redact(p) for p in providers.list_providers()]}

@app.post("/api/providers")
def create_provider(req: ProviderCreateRequest, request: Request, user: str = Depends(auth.get_current_user), x_owner_key: Optional[str] = Header(default=None)):
    _require_owner(user, x_owner_key)
    ratelimit.enforce(request, "add_provider", limit=20, window_seconds=300)
    cfg = {k: v for k, v in req.dict().items() if v is not None}
    try:
        created = providers.add_provider(cfg)
    except providers.ProviderError as e:
        raise HTTPException(400, str(e)) from e
    return providers.redact(created)

@app.delete("/api/providers/{provider_id}")
def delete_provider(provider_id: str, user: str = Depends(auth.get_current_user), x_owner_key: Optional[str] = Header(default=None)):
    _require_owner(user, x_owner_key)
    try:
        providers.remove_provider(provider_id)
    except providers.ProviderError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}

@app.post("/api/session")
def create_session(user: str = Depends(auth.get_current_user)):
    return {"session_id": sessions.new_session_id()}

@app.delete("/api/session/{session_id}")
def clear_session(session_id: str, user: str = Depends(auth.get_current_user)):
    sessions.clear(_skey(user, session_id))
    return {"ok": True}

@app.post("/api/chat")
def chat(req: ChatRequest, user: str = Depends(auth.get_current_user)):
    resolved = req.agent
    if resolved == "auto":
        try:
            resolved = router.route(req.message, has_image=bool(req.image_b64))
        except providers.ProviderError as e:
            raise HTTPException(502, str(e)) from e
    if not _valid_agent(resolved):
        raise HTTPException(400, f"unknown provider '{req.agent}'")
    cost = credits.DEFAULT_COST["chat"]
    _charge_or_402(user, cost, "chat")
    session_id = req.session_id or sessions.new_session_id()
    skey = _skey(user, session_id)
    context = sessions.as_transcript(skey) if sessions.get_history(skey) else None
    history = sessions.as_glm_messages(skey, req.message)
    try:
        reply = providers.call(resolved, req.message, session_id=session_id, context=context, image_b64=req.image_b64, history=history)
    except providers.ProviderError as e:
        credits.refund(user, cost, "chat")
        raise HTTPException(502, str(e)) from e
    sessions.append(skey, "user", req.message)
    sessions.append(skey, "assistant", reply)
    return {"reply": reply, "session_id": session_id, "resolved_agent": resolved}

@app.post("/api/chat/stream")
def chat_stream(req: ChatRequest, user: str = Depends(auth.get_current_user)):
    resolved = req.agent
    if resolved == "auto":
        try:
            resolved = router.route(req.message, has_image=bool(req.image_b64))
        except providers.ProviderError as e:
            raise HTTPException(502, str(e)) from e
    if not _valid_agent(resolved):
        raise HTTPException(400, f"unknown provider '{req.agent}'")
    _charge_or_402(user, credits.DEFAULT_COST["chat"], "chat")
    session_id = req.session_id or sessions.new_session_id()
    skey = _skey(user, session_id)
    context = sessions.as_transcript(skey) if sessions.get_history(skey) else None
    history = sessions.as_glm_messages(skey, req.message)
    def gen():
        yield f"{SESSION_MARK}{session_id}{SESSION_MARK}"
        if req.agent == "auto":
            yield f"{ROUTED_MARK}{resolved}{ROUTED_MARK}"
        collected = []
        try:
            for chunk in providers.call_stream(resolved, req.message, session_id=session_id, context=context, image_b64=req.image_b64, history=history):
                collected.append(chunk)
                yield chunk
        except providers.ProviderError as e:
            yield f"\n[error] {e}"
            return
        sessions.append(skey, "user", req.message)
        sessions.append(skey, "assistant", "".join(collected))
    return StreamingResponse(gen(), media_type="text/plain")

@app.post("/api/consensus")
def run_consensus_route(req: ConsensusRequest, user: str = Depends(auth.get_current_user)):
    ids = req.provider_ids or providers.list_provider_ids()
    _charge_or_402(user, credits.DEFAULT_COST["consensus"] * max(1, len(ids)), "consensus")
    session_id = req.session_id or sessions.new_session_id()
    skey = _skey(user, session_id)
    context = sessions.as_transcript(skey) if sessions.get_history(skey) else None
    try:
        result = consensus.run_consensus(req.message, context=context, provider_ids=req.provider_ids)
    except providers.ProviderError as e:
        raise HTTPException(400, str(e)) from e
    sessions.append(skey, "user", req.message)
    sessions.append(skey, "assistant", result["merged"])
    result["session_id"] = session_id
    return result

@app.get("/api/workspace/files")
def list_files(user: str = Depends(auth.get_current_user)):
    return {"files": workspace.list_files(user_id=user)}

@app.get("/api/workspace/file")
def read_file(path: str, user: str = Depends(auth.get_current_user)):
    try:
        return {"path": path, "content": workspace.read_file(path, user_id=user)}
    except workspace.WorkspaceError as e:
        raise HTTPException(404, str(e)) from e

@app.post("/api/workspace/file")
def write_file(req: FileWriteRequest, user: str = Depends(auth.get_current_user)):
    try:
        workspace.write_file(req.path, req.content, user_id=user)
        return {"ok": True, "path": req.path}
    except workspace.WorkspaceError as e:
        raise HTTPException(400, str(e)) from e

@app.delete("/api/workspace/file")
def delete_file(path: str, user: str = Depends(auth.get_current_user)):
    workspace.delete_file(path, user_id=user)
    return {"ok": True}

@app.post("/api/workspace/upload")
async def upload_zip(file: UploadFile = File(...), user: str = Depends(auth.get_current_user)):
    content = await file.read()
    try:
        extracted = workspace.import_zip(content, user_id=user)
    except Exception as e:
        raise HTTPException(400, f"could not import zip: {e}") from e
    return {"extracted": extracted}

@app.get("/api/workspace/export")
def export_zip(user: str = Depends(auth.get_current_user)):
    data = workspace.export_zip(user_id=user)
    return Response(content=data, media_type="application/zip", headers={"Content-Disposition": "attachment; filename=paradox-workspace.zip"})

@app.post("/api/snapshots")
def create_snapshot(req: SnapshotRequest, user: str = Depends(auth.get_current_user)):
    return snapshots.create(user_id=user, label=req.label)

@app.get("/api/snapshots")
def list_snapshots(user: str = Depends(auth.get_current_user)):
    return {"snapshots": snapshots.list_snapshots(user_id=user)}

@app.post("/api/snapshots/{snapshot_id}/rollback")
def rollback_snapshot(snapshot_id: str, user: str = Depends(auth.get_current_user)):
    try:
        snapshots.rollback(snapshot_id, user_id=user)
    except snapshots.SnapshotError as e:
        raise HTTPException(404, str(e)) from e
    return {"ok": True}

@app.post("/api/execute")
def execute(req: ExecuteRequest, request: Request, user: str = Depends(auth.get_current_user)):
    _require_exec_enabled()
    ratelimit.enforce(request, "execute", limit=20, window_seconds=60)
    timeout = max(1, min(req.timeout, 60))
    return executor.run_command(req.command, user_id=user, timeout=timeout)

@app.post("/api/execute/autofix")
def execute_autofix(req: AutoFixRequest, request: Request, user: str = Depends(auth.get_current_user)):
    _require_exec_enabled()
    ratelimit.enforce(request, "autofix", limit=10, window_seconds=60)
    if req.file_path:
        _charge_or_402(user, credits.DEFAULT_COST["autofix"], "autofix")
    snapshots.create(user_id=user, label="pre-autofix")
    return executor.auto_fix_run(req.command, file_path=req.file_path, user_id=user, max_attempts=req.max_attempts, timeout=req.timeout, coder_provider_id=req.coder_provider_id)

@app.get("/preview/{file_path:path}")
def preview_file(file_path: str, user: str = Depends(auth.get_current_user_flexible)):
    target = file_path or "index.html"
    try:
        full = workspace.safe_path(target, user_id=user)
    except workspace.WorkspaceError as e:
        raise HTTPException(404, str(e)) from e
    if not full.is_file():
        raise HTTPException(404, f"'{target}' not found in workspace")
    media_type, _ = mimetypes.guess_type(str(full))
    return FileResponse(full, media_type=media_type or "application/octet-stream")

@app.get("/preview")
def preview_root(user: str = Depends(auth.get_current_user_flexible)):
    return preview_file("index.html", user=user)

@app.post("/api/pipeline")
def run_pipeline_route(req: PipelineRequest, user: str = Depends(auth.get_current_user)):
    _charge_or_402(user, credits.DEFAULT_COST["pipeline"], "pipeline")
    snapshots.create(user_id=user, label="pre-pipeline")
    try:
        result = pipeline.run_pipeline(req.task, write_files=req.write_files, user_id=user, role_providers=req.role_providers)
    except pipeline.PipelineError as e:
        raise HTTPException(502, str(e)) from e
    return result

@app.post("/api/browse")
def browse(req: BrowseRequest, request: Request, user: str = Depends(auth.get_current_user)):
    _require_browse_enabled()
    ratelimit.enforce(request, "browse", limit=20, window_seconds=60)
    try:
        return browser.fetch(req.url)
    except browser.BrowserError as e:
        raise HTTPException(502, str(e)) from e

@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
