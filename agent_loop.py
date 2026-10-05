"""
Tool-calling agent loop for openai_compatible providers.

Rounds: model may emit tool_calls → we run Reach tools → feed results back
until a plain text answer or max rounds.
"""
from __future__ import annotations

from typing import Any, Generator

import config
import providers
import tools_reach


class AgentLoopError(RuntimeError):
    pass


MAX_TOOL_ROUNDS = 4


def _message_to_dict(msg: Any) -> dict:
    role = getattr(msg, "role", None) or (msg.get("role") if isinstance(msg, dict) else "assistant")
    content = getattr(msg, "content", None)
    if content is None and isinstance(msg, dict):
        content = msg.get("content")
    out: dict[str, Any] = {"role": role, "content": content}
    tool_calls = getattr(msg, "tool_calls", None)
    if tool_calls is None and isinstance(msg, dict):
        tool_calls = msg.get("tool_calls")
    if tool_calls:
        serialized = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                serialized.append(tc)
                continue
            fn = getattr(tc, "function", None)
            serialized.append({
                "id": getattr(tc, "id", "") or "",
                "type": "function",
                "function": {
                    "name": getattr(fn, "name", "") if fn else "",
                    "arguments": getattr(fn, "arguments", "") if fn else "",
                },
            })
        out["tool_calls"] = serialized
    return out


def _openai_with_tools(cfg: dict, messages: list[dict], tools: list[dict], stream: bool = False):
    from openai import OpenAI

    api_key = providers._resolve_api_key(cfg)
    if not api_key:
        raise providers.ProviderError(
            f"provider '{cfg['id']}' has no API key set (api_key_env or api_key)"
        )
    client = OpenAI(base_url=cfg["base_url"], api_key=api_key)

    def do():
        kwargs = dict(
            model=cfg["model"],
            messages=messages,
            temperature=cfg.get("temperature", 0.7),
            top_p=cfg.get("top_p", 1),
            max_tokens=cfg.get("max_tokens", 8192),
            stream=stream,
        )
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        return client.chat.completions.create(**kwargs)

    return providers._retry(do, cfg.get("max_retries", 2), f"agent '{cfg['id']}'")


def _ensure_system(messages: list[dict]) -> list[dict]:
    if messages and messages[0].get("role") == "system":
        return messages
    return [{"role": "system", "content": tools_reach.SYSTEM_HINT}] + list(messages)


def run_agent(
    provider_id: str,
    messages: list[dict],
    *,
    use_tools: bool = True,
    max_rounds: int = MAX_TOOL_ROUNDS,
) -> dict[str, Any]:
    cfg = providers.get_provider(provider_id)
    tools_on = (
        use_tools
        and getattr(config, "ENABLE_TOOLS", True)
        and getattr(config, "ENABLE_REACH", True)
        and cfg.get("kind") == "openai_compatible"
    )

    if not tools_on:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content") or ""
                break
        reply = providers.call(provider_id, last_user, history=messages)
        return {"reply": reply, "tool_trace": [], "rounds": 0}

    msgs = _ensure_system(messages)
    tools = tools_reach.TOOL_SCHEMAS
    trace: list[dict] = []

    for round_i in range(max(1, max_rounds)):
        completion = _openai_with_tools(cfg, msgs, tools, stream=False)
        msg = completion.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            text = (msg.content or "").strip()
            return {"reply": text, "tool_trace": trace, "rounds": round_i + 1}

        msgs.append(_message_to_dict(msg))
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn else ""
            raw_args = getattr(fn, "arguments", "") if fn else ""
            args = tools_reach.parse_tool_arguments(raw_args)
            result = tools_reach.run_tool(name, args)
            tc_id = getattr(tc, "id", "") or ""
            trace.append({"name": name, "arguments": args, "result_preview": result[:500]})
            msgs.append({
                "role": "tool",
                "tool_call_id": tc_id,
                "content": result,
            })

    completion = _openai_with_tools(cfg, msgs, tools=[], stream=False)
    text = (completion.choices[0].message.content or "").strip()
    return {"reply": text or "(no reply after tool rounds)", "tool_trace": trace, "rounds": max_rounds}


def stream_agent(
    provider_id: str,
    messages: list[dict],
    *,
    use_tools: bool = True,
) -> Generator[str, None, None]:
    cfg = providers.get_provider(provider_id)
    tools_on = (
        use_tools
        and getattr(config, "ENABLE_TOOLS", True)
        and getattr(config, "ENABLE_REACH", True)
        and cfg.get("kind") == "openai_compatible"
    )

    if not tools_on:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content") or ""
                break
        yield from providers.call_stream(provider_id, last_user, history=messages)
        return

    msgs = _ensure_system(messages)
    tools = tools_reach.TOOL_SCHEMAS

    for round_i in range(MAX_TOOL_ROUNDS):
        completion = _openai_with_tools(cfg, msgs, tools, stream=False)
        msg = completion.choices[0].message
        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            text = (msg.content or "").strip()
            if text:
                step = 48
                for i in range(0, len(text), step):
                    yield text[i : i + step]
            return

        names = []
        msgs.append(_message_to_dict(msg))
        for tc in tool_calls:
            fn = getattr(tc, "function", None)
            name = getattr(fn, "name", "") if fn else ""
            names.append(name)
            raw_args = getattr(fn, "arguments", "") if fn else ""
            args = tools_reach.parse_tool_arguments(raw_args)
            result = tools_reach.run_tool(name, args)
            msgs.append({
                "role": "tool",
                "tool_call_id": getattr(tc, "id", "") or "",
                "content": result,
            })
        yield f"@@TOOLS@@{','.join(names)}@@\n"

    completion = _openai_with_tools(cfg, msgs, tools=[], stream=False)
    text = (completion.choices[0].message.content or "").strip()
    step = 48
    for i in range(0, len(text), step):
        yield text[i : i + step]
