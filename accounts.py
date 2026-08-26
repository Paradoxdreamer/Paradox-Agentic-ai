"""
Paradox AI - accounts

Signup/login business logic: email+password and Google OAuth, both backed
by db.py. Only reachable when PARADOX_AUTH_MODE=accounts (server.py's
routes 404 otherwise).
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from typing import Optional
from urllib.parse import urlencode

import requests

import config
import db

PBKDF2_ITERATIONS = 390_000

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


class AccountError(RuntimeError):
    pass


def _hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), PBKDF2_ITERATIONS)
    return digest.hex(), salt


def _new_api_key() -> str:
    return "pk_" + secrets.token_urlsafe(32)


def _is_creator_email(email: str) -> bool:
    return email.lower() in [e.lower() for e in config.CREATOR_EMAILS]


def signup_email(email: str, password: str, accepted_terms: bool) -> dict:
    if not email or "@" not in email:
        raise AccountError("enter a valid email address")
    if not accepted_terms:
        raise AccountError("you must accept the Terms of Service and Privacy Policy to sign up")
    if db.get_user_by_email(email):
        raise AccountError("an account with that email already exists")
    if len(password) < 8:
        raise AccountError("password must be at least 8 characters")

    pw_hash, salt = _hash_password(password)
    return db.create_user(
        email=email,
        api_key=_new_api_key(),
        auth_provider="email",
        password_hash=pw_hash,
        password_salt=salt,
        is_creator=_is_creator_email(email),
        starting_credits=config.STARTING_CREDITS,
        accepted_terms=True,
    )


def login_email(email: str, password: str) -> dict:
    user = db.get_user_by_email(email)
    if not user or user["auth_provider"] != "email":
        raise AccountError("no email/password account with that email")
    if db.is_locked(user):
        raise AccountError("too many failed attempts -- this account is temporarily locked, try again later")
    check_hash, _ = _hash_password(password, user["password_salt"])
    if not secrets.compare_digest(check_hash, user["password_hash"]):
        db.record_failed_login(email)
        raise AccountError("incorrect password")
    db.reset_failed_login(email)
    return user


def google_login_url(redirect_uri: str, state: str) -> str:
    if not config.GOOGLE_CLIENT_ID:
        raise AccountError("Google login isn't configured (set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)")
    params = {
        "client_id": config.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


def google_callback(code: str, redirect_uri: str) -> dict:
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise AccountError("Google login isn't configured (set GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET)")

    token_resp = requests.post(
        GOOGLE_TOKEN_URL,
        data={
            "code": code,
            "client_id": config.GOOGLE_CLIENT_ID,
            "client_secret": config.GOOGLE_CLIENT_SECRET,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=15,
    )
    if not token_resp.ok:
        raise AccountError(f"Google token exchange failed: {token_resp.text[:200]}")
    access_token = token_resp.json().get("access_token")
    if not access_token:
        raise AccountError("Google didn't return an access token")

    info_resp = requests.get(
        GOOGLE_USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=15
    )
    if not info_resp.ok:
        raise AccountError(f"could not fetch Google profile: {info_resp.text[:200]}")
    info = info_resp.json()
    sub, email = info.get("sub"), info.get("email")
    if not sub or not email:
        raise AccountError("Google profile response was missing sub/email")

    existing = db.get_user_by_google_sub(sub)
    if existing:
        return existing

    if db.get_user_by_email(email):
        raise AccountError(
            "an account with this email already exists via email/password -- log in that way instead"
        )

    return db.create_user(
        email=email,
        api_key=_new_api_key(),
        auth_provider="google",
        google_sub=sub,
        display_name=info.get("name"),
        is_creator=_is_creator_email(email),
        starting_credits=config.STARTING_CREDITS,
        accepted_terms=True,
    )


def rotate_key(user_id: str) -> str:
    new_key = _new_api_key()
    db.set_api_key(user_id, new_key)
    return new_key


def public_view(user: dict) -> dict:
    return {
        "email": user["email"],
        "display_name": user.get("display_name"),
        "auth_provider": user["auth_provider"],
        "is_creator": bool(user["is_creator"]),
        "unlimited_credits": bool(user["unlimited_credits"]),
        "credits": user["credits"],
        "api_key": user["api_key"],
    }


def _oauth_secret() -> bytes:
    return (config.GOOGLE_CLIENT_SECRET or config.OWNER_KEY or "paradox-oauth-dev").encode()


def make_oauth_state() -> str:
    nonce = secrets.token_urlsafe(16)
    ts = str(int(time.time()))
    raw = f"{ts}.{nonce}"
    sig = hmac.new(_oauth_secret(), raw.encode(), hashlib.sha256).hexdigest()
    return f"{raw}.{sig}"


def check_oauth_state(state: Optional[str], max_age: int = 600) -> bool:
    if not state or state.count(".") < 2:
        return False
    ts, nonce, sig = state.split(".", 2)
    raw = f"{ts}.{nonce}"
    expect = hmac.new(_oauth_secret(), raw.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expect, sig):
        return False
    try:
        return abs(time.time() - int(ts)) <= max_age
    except ValueError:
        return False
