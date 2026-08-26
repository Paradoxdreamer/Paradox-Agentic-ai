"""
Paradox AI - credits

Simple per-call credit metering, enforced only when PARADOX_AUTH_MODE=accounts.
"""
from __future__ import annotations

import db

DEFAULT_COST = {
    "chat": 1,
    "consensus": 1,
    "pipeline": 3,
    "autofix": 1,
}


class InsufficientCreditsError(RuntimeError):
    pass


def check_and_charge(user_id: str, amount: int, kind: str) -> None:
    """
    No-op if `user_id` isn't a DB-backed account.
    Debit is atomic so two parallel requests cannot both overdraw.
    """
    user = db.get_user(user_id)
    if user is None:
        return
    if user["unlimited_credits"]:
        db.log_usage(user_id, kind, 0)
        return
    ok, remaining = db.debit_if_enough(user_id, amount)
    if not ok:
        raise InsufficientCreditsError(
            f"not enough credits ({remaining} left, {kind} costs {amount})"
        )
    db.log_usage(user_id, kind, amount)


def refund(user_id: str, amount: int, kind: str) -> None:
    user = db.get_user(user_id)
    if user is None or user["unlimited_credits"]:
        return
    db.adjust_credits(user_id, amount)
    db.log_usage(user_id, f"{kind}_refund", -amount)
