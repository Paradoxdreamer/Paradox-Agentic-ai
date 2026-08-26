"""
Paradox AI - owner identity

You are the owner if ANY of these is true:

1. CREATOR_EMAILS includes the email you signed up with
   (accounts mode). Those users get is_creator=1 automatically.
2. You send header X-Owner-Key matching PARADOX_OWNER_KEY.
   Use this when you have not set up accounts yet.
3. PARADOX_ALLOW_LOCAL_PROVIDER_EDIT=1 and AUTH_MODE=none
   (laptop-only convenience; do not use this on a public host).

CLI add-provider / remove-provider always works on the machine
because it writes providers.json directly -- that is you on the server.
The HTTP form is what strangers could abuse, so that is gated here.
"""
from __future__ import annotations

from typing import Optional

import config


def owner_key_matches(provided: Optional[str]) -> bool:
    if not config.OWNER_KEY or not provided:
        return False
    if len(provided) != len(config.OWNER_KEY):
        return False
    acc = 0
    for a, b in zip(provided.encode(), config.OWNER_KEY.encode()):
        acc |= a ^ b
    return acc == 0


def is_owner(user_id: str, owner_key: Optional[str] = None) -> bool:
    if owner_key_matches(owner_key):
        return True
    if config.AUTH_MODE == "accounts":
        import db
        user = db.get_user(user_id)
        if user and (user.get("is_creator") or user.get("unlimited_credits")):
            return True
        return False
    if config.AUTH_MODE == "none" and config.ALLOW_LOCAL_PROVIDER_EDIT:
        return True
    return False


def owner_setup_hint() -> str:
    bits = []
    if config.OWNER_KEY:
        bits.append("PARADOX_OWNER_KEY is set -- paste it in the owner-key field")
    if config.CREATOR_EMAILS:
        bits.append("sign up with " + ", ".join(config.CREATOR_EMAILS))
    if config.ALLOW_LOCAL_PROVIDER_EDIT and config.AUTH_MODE == "none":
        bits.append("local provider edits are enabled")
    if not bits:
        return (
            "No owner is configured yet. Set CREATOR_EMAILS=you@email.com "
            "or PARADOX_OWNER_KEY=a-long-secret in .env, then restart."
        )
    return "Owner unlock: " + " | ".join(bits)
