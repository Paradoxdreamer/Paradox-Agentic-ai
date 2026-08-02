"""
Paradox AI - router

Auto-routing: picks which registered provider should handle a message when
"auto" is selected. Uses one provider (default: "glm") as a fast classifier,
built from the live provider list and each provider's own "description"
field -- so a newly added provider is automatically considered, no code
changes needed.

This is a heuristic, not a guarantee. If the classifier call fails or
returns something unrecognized, it falls back to the router provider
itself. You can always bypass it by picking a provider directly.
"""
from __future__ import annotations

import providers

ROUTER_PROMPT = """You are a router choosing which AI backend should answer a user's message.
Reply with EXACTLY one id from this list, and nothing else: {ids}

Backends:
{guidance}

Message: {message}
"""


def route(message: str, has_image: bool = False, router_provider_id: str = "glm") -> str:
    all_providers = providers.list_providers()
    if not all_providers:
        raise providers.ProviderError("no providers registered")

    if has_image:
        for p in all_providers:
            if p.get("supports_images"):
                return p["id"]

    guidance = "\n".join(f"- {p['id']}: {p.get('description', '')}" for p in all_providers)
    ids = ", ".join(p["id"] for p in all_providers)
    prompt = ROUTER_PROMPT.format(ids=ids, guidance=guidance, message=message)

    classifier_id = router_provider_id if any(p["id"] == router_provider_id for p in all_providers) else all_providers[0]["id"]

    try:
        reply = providers.call(classifier_id, prompt)
    except providers.ProviderError:
        return classifier_id

    reply = (reply or "").strip().lower()
    for p in all_providers:
        if p["id"].lower() in reply:
            return p["id"]
    return classifier_id
