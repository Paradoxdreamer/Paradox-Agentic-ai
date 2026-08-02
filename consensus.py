"""
Paradox AI - consensus

Sends the same message to a set of providers in parallel (default: every
registered provider) and merges their answers into one synthesized reply.
All raw drafts are returned alongside the merge, so you can see where
providers agreed or diverged instead of trusting the merge blindly.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import providers

MERGE_PROMPT = """Several different AI assistants were each asked the same question. Read
their drafts below and write ONE best final answer that combines their
strengths and resolves disagreements (note briefly if there was a
meaningful disagreement). Do not mention that this came from multiple
drafts or name the assistants.

Question: {message}

{drafts}
"""


def run_consensus(
    message: str,
    context: Optional[str] = None,
    provider_ids: Optional[list[str]] = None,
    merge_provider_id: str = "glm",
) -> dict:
    all_ids = provider_ids or providers.list_provider_ids()
    if not all_ids:
        raise providers.ProviderError("no providers registered")

    drafts: dict[str, Optional[str]] = {}
    errors: dict[str, str] = {}

    def job(pid: str):
        return providers.call(pid, message, context=context)

    with ThreadPoolExecutor(max_workers=max(1, len(all_ids))) as ex:
        futures = {ex.submit(job, pid): pid for pid in all_ids}
        for fut in as_completed(futures):
            pid = futures[fut]
            try:
                drafts[pid] = fut.result()
            except providers.ProviderError as e:
                errors[pid] = str(e)
                drafts[pid] = None

    draft_text = "\n\n".join(f"--- {pid} ---\n{drafts[pid] or '(no response)'}" for pid in all_ids)

    merge_id = merge_provider_id if merge_provider_id in all_ids or merge_provider_id in providers.list_provider_ids() else all_ids[0]
    try:
        merged = providers.call(merge_id, MERGE_PROMPT.format(message=message, drafts=draft_text))
    except providers.ProviderError as e:
        merged = f"[merge failed: {e}]"

    return {"drafts": drafts, "errors": errors, "merged": merged}
