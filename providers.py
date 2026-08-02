"""
Paradox AI - providers

Generic AI backend registry. New providers (another omegatech endpoint, a
different NVIDIA/OpenAI-compatible model, literally any API you have a
token for) get added by editing providers.json, or via the "Add provider"
form in the UI / POST /api/providers -- no code changes needed.

Two provider "kinds" are supported out of the box, which between them cover
most AI APIs you'll run into:

  "http_get"          a simple GET endpoint that takes a text/message query
                       param and returns text or JSON. This is the shape of
                       the omegatech endpoints -- point another omegatech
                       route (or anything with a similar shape) at this by
                       setting base_url/path/message_param.

  "openai_compatible"  any OpenAI-compatible /v1/chat/completions API:
                        NVIDIA NIM, OpenAI itself, Groq, Together, a local
                        Ollama/vLLM server, etc. Set base_url + model +
                        an API key.

providers.json seeds with the three backends from the original setup the
first time this runs. Edit that file directly, or use add_provider()/the
API, any time.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Generator, Optional

import requests

PROVIDERS_FILE = Path(__file__).parent / "providers.json"

RESERVED_IDS = {"auto", "consensus"}  # special chat modes, can't double as provider ids

_LIKELY_TEXT_KEYS = ("response", "reply", "message", "text", "result", "answer", "content", "output")

DEFAULT_PROVIDERS = [
    {
        "id": "claude",
        "name": "Claude Proxy (omegatech)",
        "description": "Third-party proxy, unofficial. General-purpose default for writing and code.",
        "kind": "http_get",
        "base_url": "https://omegatech-api.dixonomega.tech/api/ai",
        "path": "/Claude",
        "message_param": "text",
        "supports_streaming": False,
        "supports_images": False,
        "max_retries": 2,
        "timeout": 60,
    },
    {
        "id": "gpt4mini",
        "name": "GPT-4-mini (omegatech)",
        "description": "Third-party proxy, unofficial. Supports images and its own sessions.",
        "kind": "http_get",
        "base_url": "https://omegatech-api.dixonomega.tech/api/ai",
        "path": "/Gpt-4-mini",
        "message_param": "message",
        "session_param": "session",
        "image_param": "image",
        "supports_streaming": False,
        "supports_images": True,
        "max_retries": 2,
        "timeout": 60,
    },
    {
        "id": "glm",
        "name": "GLM-5.2 (NVIDIA NIM)",
        "description": "Fast, streams responses. Good default for general chat and planning.",
        "kind": "openai_compatible",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "z-ai/glm-5.2",
        "api_key_env": "NVIDIA_API_KEY",
        "supports_streaming": True,
        "supports_images": False,
        "max_retries": 2,
        "timeout": 60,
    },
]


class ProviderError(RuntimeError):
    pass


def _load() -> list[dict]:
    if not PROVIDERS_FILE.exists():
        PROVIDERS_FILE.write_text(json.dumps(DEFAULT_PROVIDERS, indent=2))
        return list(DEFAULT_PROVIDERS)
    try:
        return json.loads(PROVIDERS_FILE.read_text())
    except (json.JSONDecodeError, OSError) as e:
        raise ProviderError(f"providers.json is unreadable: {e}") from e


def _save(providers_list: list[dict]) -> None:
    PROVIDERS_FILE.write_text(json.dumps(providers_list, indent=2))


def list_providers() -> list[dict]:
    """Full config for every registered provider, read fresh from disk each call."""
    return _load()


def list_provider_ids() -> list[str]:
    return [p["id"] for p in _load()]


def get_provider(provider_id: str) -> dict:
    for p in _load():
        if p["id"] == provider_id:
            return p
    raise ProviderError(f"unknown provider '{provider_id}'")


def add_provider(cfg: dict) -> dict:
    providers_list = _load()
    pid = cfg.get("id")
    if not pid:
        raise ProviderError("provider needs an 'id'")
    if pid in RESERVED_IDS:
        raise ProviderError(f"'{pid}' is reserved (used by auto-route/consensus modes)")
    if any(p["id"] == pid for p in providers_list):
        raise ProviderError(f"provider id '{pid}' already exists")
    if cfg.get("kind") not in ("http_get", "openai_compatible"):
        raise ProviderError("kind must be 'http_get' or 'openai_compatible'")
    if cfg["kind"] == "openai_compatible" and not cfg.get("model"):
        raise ProviderError("openai_compatible providers need a 'model'")
    if not cfg.get("base_url"):
        raise ProviderError("provider needs a 'base_url'")

    cfg.setdefault("name", pid)
    cfg.setdefault("description", "")
    cfg.setdefault("supports_streaming", cfg["kind"] == "openai_compatible")
    cfg.setdefault("supports_images", False)
    cfg.setdefault("max_retries", 2)
    cfg.setdefault("timeout", 60)
    providers_list.append(cfg)
    _save(providers_list)
    return cfg


def remove_provider(provider_id: str) -> None:
    providers_list = _load()
    remaining = [p for p in providers_list if p["id"] != provider_id]
    if len(remaining) == len(providers_list):
        raise ProviderError(f"unknown provider '{provider_id}'")
    _save(remaining)


def redact(cfg: dict) -> dict:
    """Copy of a provider config safe to send to a browser (no raw api_key)."""
    out = dict(cfg)
    if out.get("api_key"):
        out["api_key"] = "***"
    return out


# ---------- execution ----------

def _extract_text(data) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in _LIKELY_TEXT_KEYS:
            if key in data and isinstance(data[key], str):
                return data[key]
        choices = data.get("choices")
        if isinstance(choices, list) and choices:
            first = choices[0]
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                    return msg["content"]
                if isinstance(first.get("text"), str):
                    return first["text"]
        return json.dumps(data)
    return str(data)


def _retry(fn, max_retries: int, label: str):
    """Retries fn() on connection errors/timeouts/5xx with exponential backoff. 4xx fails fast."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status is not None and status < 500:
                raise ProviderError(f"{label}: HTTP {status}") from e
            last_err = e
        except requests.exceptions.RequestException as e:
            last_err = e
        if attempt < max_retries:
            time.sleep(1.5 ** attempt)
    raise ProviderError(f"{label} failed after {max_retries + 1} attempt(s): {last_err}")


def _resolve_api_key(cfg: dict) -> Optional[str]:
    if cfg.get("api_key"):
        return cfg["api_key"]
    if cfg.get("api_key_env"):
        return os.getenv(cfg["api_key_env"])
    return None


def _call_http_get(cfg: dict, message: str, session_id=None, context=None, image_b64=None) -> str:
    url = cfg["base_url"].rstrip("/") + cfg.get("path", "")
    full_message = f"{context}\nUser: {message}" if context else message
    params = {cfg.get("message_param", "text"): full_message}
    if session_id and cfg.get("session_param"):
        params[cfg["session_param"]] = session_id
    if image_b64 and cfg.get("image_param"):
        params[cfg["image_param"]] = image_b64

    api_key = _resolve_api_key(cfg)
    headers = {}
    if api_key and cfg.get("api_key_header"):
        headers[cfg["api_key_header"]] = api_key
    elif api_key:
        params.setdefault(cfg.get("api_key_param", "api_key"), api_key)

    def do():
        r = requests.get(url, params=params, headers=headers, timeout=cfg.get("timeout", 60))
        r.raise_for_status()
        return r

    r = _retry(do, cfg.get("max_retries", 2), f"provider '{cfg['id']}'")
    try:
        data = r.json()
    except ValueError:
        return r.text
    return _extract_text(data)


def _call_openai_compatible(cfg: dict, messages: list[dict], stream: bool):
    from openai import OpenAI

    api_key = _resolve_api_key(cfg)
    if not api_key:
        raise ProviderError(f"provider '{cfg['id']}' has no API key set (api_key_env or api_key)")

    client = OpenAI(base_url=cfg["base_url"], api_key=api_key)

    def do():
        return client.chat.completions.create(
            model=cfg["model"],
            messages=messages,
            temperature=cfg.get("temperature", 1),
            top_p=cfg.get("top_p", 1),
            max_tokens=cfg.get("max_tokens", 16384),
            stream=stream,
        )

    completion = _retry(do, cfg.get("max_retries", 2), f"provider '{cfg['id']}'")

    if not stream:
        return completion.choices[0].message.content or ""

    def _gen():
        for chunk in completion:
            if not getattr(chunk, "choices", None):
                continue
            choice = chunk.choices[0]
            delta = getattr(choice, "delta", None)
            if delta is not None and getattr(delta, "content", None):
                yield delta.content

    return _gen()


def call(
    provider_id: str,
    message: str,
    session_id: Optional[str] = None,
    context: Optional[str] = None,
    image_b64: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> str:
    """Non-streaming call. Works uniformly across provider kinds."""
    cfg = get_provider(provider_id)
    if cfg["kind"] == "http_get":
        return _call_http_get(cfg, message, session_id=session_id, context=context, image_b64=image_b64)
    if cfg["kind"] == "openai_compatible":
        msgs = history if history is not None else [{"role": "user", "content": message}]
        return _call_openai_compatible(cfg, msgs, stream=False)
    raise ProviderError(f"unknown provider kind '{cfg['kind']}'")


def call_stream(
    provider_id: str,
    message: str,
    session_id: Optional[str] = None,
    context: Optional[str] = None,
    image_b64: Optional[str] = None,
    history: Optional[list[dict]] = None,
) -> Generator[str, None, None]:
    """Streaming call. Providers that don't support streaming yield one full-text chunk."""
    cfg = get_provider(provider_id)
    if cfg["kind"] == "openai_compatible" and cfg.get("supports_streaming", True):
        msgs = history if history is not None else [{"role": "user", "content": message}]
        yield from _call_openai_compatible(cfg, msgs, stream=True)
    else:
        yield call(
            provider_id, message, session_id=session_id, context=context,
            image_b64=image_b64, history=history,
        )
