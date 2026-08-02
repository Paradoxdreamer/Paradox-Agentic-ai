"""
Paradox AI - executor

Runs a shell command inside a user's workspace and captures output.

*** SECURITY WARNING ***
This executes real commands with the same OS privileges as the Paradox AI
server process. The only guardrails here are a working-directory
restriction and a timeout -- there is NO sandboxing (no container, no
seccomp, no resource limits beyond time). Since the commands being run are
code an LLM wrote, treat this the same as running code you found on the
internet: do not point a server with this enabled at untrusted users, and
consider running the whole server inside a container (Docker, firejail,
gVisor, a disposable VM) if you want it to survive a bad generation.

Also offers an auto-fix loop: run a command, and if it fails, hand the
error and the file back to the coder agent for a fix, write the fix, and
retry -- up to max_attempts total runs. A snapshot should be taken by the
caller (see snapshots.py) before using this, so a bad auto-fix can be
rolled back.
"""
from __future__ import annotations

import subprocess
from typing import Optional

import pipeline
import providers
import workspace

DEFAULT_TIMEOUT = 20


def run_command(command: str, user_id: str = "default", timeout: int = DEFAULT_TIMEOUT) -> dict:
    cwd = workspace.user_root(user_id)
    try:
        proc = subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as e:
        return {
            "command": command,
            "stdout": e.stdout or "",
            "stderr": (e.stderr or "") + f"\n[timed out after {timeout}s]",
            "returncode": None,
        }
    return {"command": command, "stdout": proc.stdout, "stderr": proc.stderr, "returncode": proc.returncode}


AUTOFIX_PROMPT = (
    "The following file failed to run. Fix it and output ONLY the corrected "
    "file using exactly this format:\n\n// FILE: {path}\n<full corrected content>\n\n"
    "File path: {path}\n\nCurrent content:\n{content}\n\n"
    "Command used to run it: {command}\n\nError output:\n{error}"
)


def auto_fix_run(
    command: str,
    file_path: Optional[str] = None,
    user_id: str = "default",
    max_attempts: int = 3,
    timeout: int = DEFAULT_TIMEOUT,
    coder_provider_id: str = "claude",
) -> dict:
    """
    Runs `command`, and if it fails and `file_path` is given, sends the
    error plus current file content to `coder_provider_id` for a fix, writes
    the fix, and retries. Stops early if the provider doesn't return a
    recognizable file block, or max_attempts is reached.
    """
    attempts = []
    for i in range(max_attempts):
        result = run_command(command, user_id=user_id, timeout=timeout)
        attempts.append(result)
        if result["returncode"] == 0:
            return {"success": True, "attempts": attempts}
        if not file_path or i == max_attempts - 1:
            break
        try:
            current = workspace.read_file(file_path, user_id=user_id)
        except workspace.WorkspaceError:
            break
        prompt = AUTOFIX_PROMPT.format(
            path=file_path,
            content=current,
            command=command,
            error=result["stderr"] or result["stdout"],
        )
        try:
            fix = providers.call(coder_provider_id, prompt)
        except providers.ProviderError:
            break
        files = pipeline.extract_files(fix)
        if file_path in files:
            workspace.write_file(file_path, files[file_path], user_id=user_id)
        else:
            break  # provider didn't follow the format -- nothing to apply

    return {"success": False, "attempts": attempts}
