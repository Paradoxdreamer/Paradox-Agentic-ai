"""
Paradox AI - credits

Simple per-call credit metering, enforced only when PARADOX_AUTH_MODE=accounts.
Costs are flat and coarse (per API call, not per token/per provider cost) --
a v1 model, easy to refine into real per-token accounting later once you
have usage data to calibrate against.
"""
from __future__ import annotations

import db

DEFAULT_COST = {
    "chat": 1,
    "consensus": 1,   # multiplied by number of providers queried by the caller
    "pipeline": 3,     # one per role (architect/coder/reviewer)
    "autofix": 1,      # per invocation, regardless of retry attempts
}


class InsufficientCreditsError(RuntimeError):
    pass


def check_and_charge(user_id: str, amount: int, kind: str) -> None:
    """
    No-op if `user_id` isn't a DB-backed account (e.g. "default" in
    non-accounts modes) -- credits are fully inert unless PARADOX_AUTH_MODE
    is "accounts" AND the user actually has an account row.
    """
    user = db.get_user(user_id)
    if user is None:
        return
    if user["unlimited_credits"]:
        db.log_usage(user_id, kind, 0)
        return
    if user["credits"] < amount:
        raise InsufficientCreditsError(
            f"not enough credits ({user['credits']} left, {kind} costs {amount})"
        )
    db.adjust_credits(user_id, -amount)
    db.log_usage(user_id, kind, amount)
