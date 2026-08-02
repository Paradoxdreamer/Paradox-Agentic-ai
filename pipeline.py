"""
Paradox AI - pipeline

Chains providers into fixed roles to go from a task description to written
files in the workspace:

    architect  -> plan + file list
    coder      -> full file contents
    reviewer   -> issues + corrected files (optional)

Each role defaults to one of the three built-in providers (glm / claude /
gpt4mini) but can be pointed at ANY registered provider id via
role_providers -- so a provider you add through providers.json or the "Add
provider" form can immediately fill any role, no code changes needed.

Agents are asked to emit files using a plain marker convention:

    // FILE: path/to/file.ext
    <file content>

which extract_files() parses out and workspace.write_file() persists.
This convention is enforced only by prompting -- if a backend ignores it,
that step just won't produce files, and the result reports exactly what
got written so you can check.
"""
from __future__ import annotations

import re
from typing import Optional

import providers
import workspace

FILE_BLOCK_RE = re.compile(
    r"//\s*FILE:\s*(?P<path>[^\n]+)\n(?P<body>.*?)(?=\n//\s*FILE:|\Z)",
    re.DOTALL,
)

DEFAULT_ROLE_PROVIDERS = {"architect": "glm", "coder": "claude", "reviewer": "gpt4mini"}

ARCHITECT_PROMPT = (
    "You are the architect on a small build team. Given the task below, "
    "produce a short plan: the overall approach, and a bullet list of the "
    "files that need to be created with their paths. Do not write full code "
    "yet -- just the plan and file list.\n\nTask: {task}"
)

CODER_PROMPT = (
    "You are the coder on a small build team. Based on the plan below, write "
    "the complete, working code for every file it lists. Output EACH file "
    "using exactly this format, with no other commentary before, between, or "
    "after the blocks:\n\n// FILE: relative/path.ext\n<full file content>\n\n"
    "Task: {task}\n\nPlan:\n{plan}"
)

REVIEWER_PROMPT = (
    "You are the reviewer on a small build team. Review the code below for "
    "bugs, missing pieces, or things that won't run. Start with a short list "
    "of issues found (or say 'No issues found'). If there are fixes, output "
    "the corrected files using the same format as before:\n\n"
    "// FILE: relative/path.ext\n<full corrected file content>\n\n"
    "Task: {task}\n\nCode:\n{code}"
)


class PipelineError(RuntimeError):
    pass


def extract_files(text: str) -> dict[str, str]:
    files = {}
    for m in FILE_BLOCK_RE.finditer(text):
        path = m.group("path").strip()
        body = m.group("body").strip("\n")
        if path:
            files[path] = body
    return files


def _call(provider_id: str, prompt: str) -> str:
    try:
        return providers.call(provider_id, prompt)
    except providers.ProviderError as e:
        raise PipelineError(f"{provider_id} step failed: {e}") from e


def run_pipeline(
    task: str,
    write_files: bool = True,
    user_id: str = "default",
    role_providers: Optional[dict[str, str]] = None,
) -> dict:
    roles = dict(DEFAULT_ROLE_PROVIDERS)
    if role_providers:
        roles.update({k: v for k, v in role_providers.items() if v})

    steps = []

    plan = _call(roles["architect"], ARCHITECT_PROMPT.format(task=task))
    steps.append({"role": "architect", "agent": roles["architect"], "output": plan})

    code = _call(roles["coder"], CODER_PROMPT.format(task=task, plan=plan))
    steps.append({"role": "coder", "agent": roles["coder"], "output": code})
    files = extract_files(code)

    review = _call(roles["reviewer"], REVIEWER_PROMPT.format(task=task, code=code))
    steps.append({"role": "reviewer", "agent": roles["reviewer"], "output": review})
    files.update(extract_files(review))  # reviewer's corrections win

    written = []
    if write_files:
        for path, content in files.items():
            try:
                workspace.write_file(path, content, user_id=user_id)
                written.append(path)
            except workspace.WorkspaceError:
                continue

    return {
        "task": task,
        "role_providers": roles,
        "steps": steps,
        "files_found": list(files.keys()),
        "files_written": written,
    }
