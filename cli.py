#!/usr/bin/env python3
"""
Paradox AI - CLI

    python cli.py providers                        # list registered providers
    python cli.py add-provider provider.json        # register a new one from a JSON file
    python cli.py remove-provider some-id
    python cli.py chat glm "build me a landing page for a coffee shop"
    python cli.py chat auto "explain this stack trace"
    python cli.py consensus "what's the best way to cache this?"
    python cli.py ls
    python cli.py cat index.html
    python cli.py write notes.txt "hello workspace"
    python cli.py import-zip site.zip
    python cli.py export-zip out.zip
    python cli.py browse https://example.com
    python cli.py pipeline "a single page portfolio site"
    python cli.py snapshot --label before-refactor
    python cli.py snapshots
    python cli.py rollback 20260801T120000
    python cli.py exec "python3 app.py"
    python cli.py autofix "python3 app.py" --file app.py
    python cli.py repl

Example provider.json for add-provider (an OpenAI-compatible endpoint):
    {
      "id": "groq-llama",
      "name": "Llama on Groq",
      "kind": "openai_compatible",
      "base_url": "https://api.groq.com/openai/v1",
      "model": "llama-3.3-70b-versatile",
      "api_key_env": "GROQ_API_KEY",
      "supports_streaming": true
    }
"""
from __future__ import annotations

import argparse
import json
import sys

import browser
import config
import consensus
import executor
import pipeline
import providers
import router
import sessions
import snapshots
import workspace

BANNER = f"""
{config.APP_NAME}
{config.APP_TAGLINE}
"""


def cmd_users(_args):
    import db
    users = db.list_users()
    if not users:
        print("no accounts yet")
        return
    for u in users:
        credits_str = "unlimited" if u["unlimited_credits"] else str(u["credits"])
        creator = " [creator]" if u["is_creator"] else ""
        print(f"{u['email']:<32} {u['auth_provider']:<8} credits={credits_str}{creator}")


def cmd_grant_unlimited(args):
    import db
    if db.grant_unlimited(args.email):
        print(f"granted unlimited credits to {args.email}")
    else:
        print(f"[error] no account found for {args.email} (they need to sign up first)", file=sys.stderr)
        sys.exit(1)


def cmd_add_credits(args):
    import db
    user = db.get_user_by_email(args.email)
    if not user:
        print(f"[error] no account found for {args.email}", file=sys.stderr)
        sys.exit(1)
    db.adjust_credits(user["id"], args.amount)
    print(f"adjusted {args.email} by {args.amount:+d} credits")


def cmd_providers(_args):
    for p in providers.list_providers():
        flags = []
        if p.get("supports_streaming"):
            flags.append("streams")
        if p.get("supports_images"):
            flags.append("images")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"{p['id']:<16} {p.get('kind'):<18} {p.get('name','')}{flag_str}")
        if p.get("description"):
            print(f"{'':<16} {p['description']}")


def cmd_add_provider(args):
    with open(args.json_file) as f:
        cfg = json.load(f)
    try:
        created = providers.add_provider(cfg)
    except providers.ProviderError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"added provider '{created['id']}'")


def cmd_remove_provider(args):
    try:
        providers.remove_provider(args.provider_id)
    except providers.ProviderError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"removed provider '{args.provider_id}'")


def cmd_chat(args):
    resolved = args.agent
    if resolved == "auto":
        try:
            resolved = router.route(args.message)
        except providers.ProviderError as e:
            print(f"[error] {e}", file=sys.stderr)
            sys.exit(1)
        print(f"[routed to {resolved}]")
    try:
        cfg = providers.get_provider(resolved)
        if cfg.get("supports_streaming") and not args.no_stream:
            for chunk in providers.call_stream(resolved, args.message, session_id=args.session):
                print(chunk, end="", flush=True)
            print()
        else:
            print(providers.call(resolved, args.message, session_id=args.session))
    except providers.ProviderError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_consensus(args):
    try:
        result = consensus.run_consensus(args.message)
    except providers.ProviderError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    for name, draft in result["drafts"].items():
        print(f"\n=== {name} ===")
        print(draft if draft is not None else f"[error: {result['errors'].get(name)}]")
    print("\n=== merged ===")
    print(result["merged"])


def cmd_snapshot(args):
    meta = snapshots.create(label=args.label)
    print(f"created snapshot {meta['id']}")


def cmd_snapshots(_args):
    for s in snapshots.list_snapshots():
        print(f"{s['id']}  ({s['created']})")


def cmd_rollback(args):
    try:
        snapshots.rollback(args.snapshot_id)
    except snapshots.SnapshotError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"rolled back to {args.snapshot_id}")


def cmd_exec(args):
    result = executor.run_command(args.cmd, timeout=args.timeout)
    if result["stdout"]:
        print(result["stdout"], end="")
    if result["stderr"]:
        print(result["stderr"], end="", file=sys.stderr)
    print(f"[exit {result['returncode']}]")


def cmd_autofix(args):
    snapshots.create(label="pre-autofix")
    result = executor.auto_fix_run(
        args.cmd, file_path=args.file, max_attempts=args.max_attempts,
        timeout=args.timeout, coder_provider_id=args.coder,
    )
    for i, attempt in enumerate(result["attempts"], 1):
        print(f"\n--- attempt {i} (exit {attempt['returncode']}) ---")
        if attempt["stdout"]:
            print(attempt["stdout"], end="")
        if attempt["stderr"]:
            print(attempt["stderr"], end="", file=sys.stderr)
    print(f"\n[{'succeeded' if result['success'] else 'gave up'} after {len(result['attempts'])} attempt(s)]")


def cmd_ls(_args):
    for f in workspace.list_files():
        print(f)


def cmd_cat(args):
    try:
        print(workspace.read_file(args.path))
    except workspace.WorkspaceError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)


def cmd_write(args):
    workspace.write_file(args.path, args.content)
    print(f"wrote {args.path}")


def cmd_import_zip(args):
    with open(args.zip_path, "rb") as f:
        extracted = workspace.import_zip(f.read())
    print(f"extracted {len(extracted)} files")
    for f in extracted:
        print(" ", f)


def cmd_export_zip(args):
    data = workspace.export_zip()
    with open(args.out_path, "wb") as f:
        f.write(data)
    print(f"wrote {args.out_path}")


def cmd_browse(args):
    try:
        result = browser.fetch(args.url)
    except browser.BrowserError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)
    print(f"# {result['title']}\n")
    print(result["text"])


def cmd_pipeline(args):
    try:
        result = pipeline.run_pipeline(args.task, write_files=not args.no_write)
    except pipeline.PipelineError as e:
        print(f"[error] {e}", file=sys.stderr)
        sys.exit(1)

    for step in result["steps"]:
        print(f"\n=== {step['role']} ({step['agent']}) ===")
        print(step["output"])

    print(f"\n=== files ===")
    if result["files_written"]:
        for f in result["files_written"]:
            print(f"  wrote {f}")
    else:
        print("  none written (providers didn't emit // FILE: blocks, or --no-write was set)")


def cmd_repl(_args):
    print(BANNER)
    ids = providers.list_provider_ids()
    print(f"providers: {', '.join(ids)}, auto  |  '/agent <id>' to switch, 'exit' to quit")
    current_agent = ids[0] if ids else "auto"
    session_id = sessions.new_session_id()
    while True:
        try:
            line = input(f"[{current_agent}]> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("exit", "quit"):
            break
        if line.startswith("/agent "):
            name = line.split(" ", 1)[1].strip()
            if name == "auto" or name in providers.list_provider_ids():
                current_agent = name
                print(f"switched to {name}")
            else:
                print(f"unknown provider, choose from {providers.list_provider_ids()} or 'auto'")
            continue
        if line == "/forget":
            sessions.clear(session_id)
            print("memory cleared")
            continue
        if line == "/providers":
            cmd_providers(None)
            continue

        resolved = current_agent
        if resolved == "auto":
            try:
                resolved = router.route(line)
                print(f"[routed to {resolved}]")
            except providers.ProviderError as e:
                print(f"[error] {e}")
                continue

        context = sessions.as_transcript(session_id) if sessions.get_history(session_id) else None
        reply_parts = []
        try:
            cfg = providers.get_provider(resolved)
            if cfg.get("supports_streaming"):
                for chunk in providers.call_stream(resolved, line, session_id=session_id, context=context):
                    print(chunk, end="", flush=True)
                    reply_parts.append(chunk)
                print()
            else:
                reply = providers.call(resolved, line, session_id=session_id, context=context)
                print(reply)
                reply_parts.append(reply)
        except providers.ProviderError as e:
            print(f"[error] {e}")
            continue
        sessions.append(session_id, "user", line)
        sessions.append(session_id, "assistant", "".join(reply_parts))


def build_parser():
    p = argparse.ArgumentParser(prog="paradox", description=BANNER)
    sub = p.add_subparsers(dest="command", required=True)

    p_prov = sub.add_parser("providers", help="list registered AI providers")
    p_prov.set_defaults(func=cmd_providers)

    p_users = sub.add_parser("users", help="list accounts (accounts mode)")
    p_users.set_defaults(func=cmd_users)

    p_grant = sub.add_parser("grant-unlimited", help="give an account unlimited credits + creator flag")
    p_grant.add_argument("email")
    p_grant.set_defaults(func=cmd_grant_unlimited)

    p_addcred = sub.add_parser("add-credits", help="adjust an account's credit balance")
    p_addcred.add_argument("email")
    p_addcred.add_argument("amount", type=int, help="can be negative")
    p_addcred.set_defaults(func=cmd_add_credits)

    p_addprov = sub.add_parser("add-provider", help="register a new provider from a JSON file")
    p_addprov.add_argument("json_file")
    p_addprov.set_defaults(func=cmd_add_provider)

    p_rmprov = sub.add_parser("remove-provider", help="unregister a provider")
    p_rmprov.add_argument("provider_id")
    p_rmprov.set_defaults(func=cmd_remove_provider)

    p_chat = sub.add_parser("chat", help="send one message to a provider (or 'auto')")
    p_chat.add_argument("agent")
    p_chat.add_argument("message")
    p_chat.add_argument("--session", default=None)
    p_chat.add_argument("--no-stream", action="store_true")
    p_chat.set_defaults(func=cmd_chat)

    p_consensus = sub.add_parser("consensus", help="ask all providers, get drafts + a merged answer")
    p_consensus.add_argument("message")
    p_consensus.set_defaults(func=cmd_consensus)

    p_ls = sub.add_parser("ls", help="list workspace files")
    p_ls.set_defaults(func=cmd_ls)

    p_cat = sub.add_parser("cat", help="print a workspace file")
    p_cat.add_argument("path")
    p_cat.set_defaults(func=cmd_cat)

    p_write = sub.add_parser("write", help="write a workspace file")
    p_write.add_argument("path")
    p_write.add_argument("content")
    p_write.set_defaults(func=cmd_write)

    p_imp = sub.add_parser("import-zip", help="extract a zip into the workspace")
    p_imp.add_argument("zip_path")
    p_imp.set_defaults(func=cmd_import_zip)

    p_exp = sub.add_parser("export-zip", help="zip the whole workspace")
    p_exp.add_argument("out_path")
    p_exp.set_defaults(func=cmd_export_zip)

    p_browse = sub.add_parser("browse", help="fetch and read a URL")
    p_browse.add_argument("url")
    p_browse.set_defaults(func=cmd_browse)

    p_pipe = sub.add_parser("pipeline", help="run task through architect -> coder -> reviewer")
    p_pipe.add_argument("task")
    p_pipe.add_argument("--no-write", action="store_true", help="don't write files to the workspace")
    p_pipe.set_defaults(func=cmd_pipeline)

    p_snap = sub.add_parser("snapshot", help="checkpoint the current workspace")
    p_snap.add_argument("--label", default=None)
    p_snap.set_defaults(func=cmd_snapshot)

    p_snaps = sub.add_parser("snapshots", help="list workspace checkpoints")
    p_snaps.set_defaults(func=cmd_snapshots)

    p_roll = sub.add_parser("rollback", help="restore the workspace to a checkpoint")
    p_roll.add_argument("snapshot_id")
    p_roll.set_defaults(func=cmd_rollback)

    p_exec = sub.add_parser("exec", help="run a command in the workspace (see executor.py safety notes)")
    p_exec.add_argument("cmd")
    p_exec.add_argument("--timeout", type=int, default=20)
    p_exec.set_defaults(func=cmd_exec)

    p_autofix = sub.add_parser("autofix", help="run a command, auto-fix + retry on failure")
    p_autofix.add_argument("cmd")
    p_autofix.add_argument("--file", default=None, help="file to hand to the coder provider on failure")
    p_autofix.add_argument("--coder", default="claude", help="provider id to use for fixes")
    p_autofix.add_argument("--max-attempts", type=int, default=3)
    p_autofix.add_argument("--timeout", type=int, default=20)
    p_autofix.set_defaults(func=cmd_autofix)

    p_repl = sub.add_parser("repl", help="interactive chat session (has memory; /agent, /forget, /providers)")
    p_repl.set_defaults(func=cmd_repl)

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
