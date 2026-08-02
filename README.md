# Paradox AI

*Allen once said: from the deepest depth of darkness comes digital innovations.*

A single console over three AI backends, with a shared workspace for
generated apps/sites and a basic web-browsing tool. Ships as a web app
today; the same core also runs as a CLI, and every route is already
REST-shaped so you can point other clients at it as a pure API later.

## ⚠️ Before you do anything else

1. **Rotate your NVIDIA API key.** If you've pasted it anywhere outside a
   `.env` file (chat, a public repo, a screenshot), treat it as compromised
   and regenerate it in the NVIDIA NIM dashboard.
2. **The "Claude" and "Gpt-4-mini" endpoints at `omegatech-api.dixonomega.tech`
   are third-party, unofficial services** — not Anthropic's or OpenAI's own
   APIs. This project treats them as unverified black boxes: response
   shape, uptime, and rate limits are unconfirmed, and the field names it
   parses (`response`, `message`, `text`, etc. — see `agents.py`) are
   best-effort guesses. If the real endpoint uses different field/param
   names, update `_extract_text()` and the `params` dicts in `agents.py`.
3. Never hardcode API keys in source files. This project only reads them
   from environment variables via `.env`.

## Setup

```bash
cd paradox_ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env and add your NVIDIA_API_KEY
```

## Run the web app

```bash
uvicorn server:app --reload --port 8000
```

Open `http://localhost:8000`. Pick an agent (top strip), chat, and the
workspace panel on the left tracks whatever files exist in `./workspace`
— import a zip of an existing app/site, or let an agent's reply guide you
to write files there (see below).

## Run the CLI

```bash
python cli.py repl                       # interactive session
python cli.py chat glm "build a landing page for a coffee shop"
python cli.py ls                         # list workspace files
python cli.py cat index.html
python cli.py write app.py "print('hi')"
python cli.py import-zip mysite.zip
python cli.py export-zip out.zip
python cli.py browse https://example.com
```

## How the three agents differ here

| name       | backend                                   | notes                                   |
|------------|--------------------------------------------|------------------------------------------|
| `claude`   | omegatech `/api/ai/Claude`                | unofficial proxy, GET + `text` param     |
| `glm`      | GLM-5.2 via NVIDIA NIM (OpenAI-compatible) | streams by default, needs `NVIDIA_API_KEY` |
| `gpt4mini` | omegatech `/api/ai/Gpt-4-mini`            | unofficial proxy, supports `session_id`, best-effort image support |

## What's new: memory, streaming, live preview, editor, pipeline

- **Chat memory** — each browser tab gets a session id (shown under the chat
  box) and every agent sees prior turns in that session, including when you
  switch agents mid-conversation. Click "forget this conversation" to reset.
  Memory lives in server process memory (`sessions.py`) — it resets on
  restart, and is shared across everyone hitting this server instance
  (there's no per-user auth yet, see below).
- **Streaming replies** — `/api/chat/stream` streams tokens as they arrive
  for GLM; the two omegatech proxy agents don't support streaming upstream,
  so their full reply arrives as one chunk, but the UI code path is identical
  either way.
- **Live preview** — the Preview tab renders whatever's at a given workspace
  path (default `index.html`) in an iframe, served raw (correct
  content-type) via `/preview/<path>`. Point it at any HTML file the agents
  or the pipeline wrote.
- **Code editor** — the Editor tab (CodeMirror, loaded from cdnjs) opens any
  workspace file for direct editing and saves back via `/api/workspace/file`.
  Click a file in the left sidebar to open it.
- **Multi-agent pipeline** — the Pipeline tab (or `python cli.py pipeline
  "<task>"`) runs a task through three fixed roles: GLM as architect (plans +
  file list), the Claude proxy as coder (writes files), GPT-4-mini as
  reviewer (finds issues, can emit corrected files). Agents are prompted to
  mark files with `// FILE: path` blocks; `pipeline.py` parses those out and
  writes them straight into the workspace. This is enforced only by
  prompting — if a backend ignores the format, that step just won't produce
  files, and the pipeline result tells you exactly what got written so you
  can check.

## Adding a new AI provider (no code changes)

This is the headline feature: **any AI backend can be plugged in through
config**, not code. Three ways to do it:

1. **Edit `providers.json` directly** — add an entry, save, refresh. Two
   provider "kinds" cover most APIs:
   - `http_get` — a GET endpoint taking a text param (the shape of the
     omegatech endpoints — use this to add another omegatech route, e.g.
     a different model they expose).
   - `openai_compatible` — any `/v1/chat/completions` API: OpenAI itself,
     Groq, Together, a local Ollama/vLLM server, or another NVIDIA NIM
     model with its own token.
2. **The "+ add provider" button** in the web UI — fills out the same
   config through a form, POSTs to `/api/providers`, shows up in the agent
   strip immediately.
3. **CLI**: `python cli.py add-provider provider.json` (see `--help` for
   the JSON shape), `python cli.py remove-provider <id>`,
   `python cli.py providers` to list what's registered.

Example — adding a Groq-hosted Llama model with its own API token:
```json
{
  "id": "groq-llama",
  "name": "Llama on Groq",
  "kind": "openai_compatible",
  "base_url": "https://api.groq.com/openai/v1",
  "model": "llama-3.3-70b-versatile",
  "api_key_env": "GROQ_API_KEY",
  "supports_streaming": true,
  "description": "fast, good for quick drafts"
}
```
Set `GROQ_API_KEY` in `.env`, add the provider, and it's usable in chat,
auto-route, consensus, and as any pipeline role — same as the three
built-ins. Auto-routing reads each provider's `description` field to decide
where a message goes, so fill that in for anything you add.

Every provider call goes through automatic retry with exponential backoff
(`max_retries`, default 2) on connection errors, timeouts, and 5xx
responses — 4xx errors (bad request, bad auth) fail immediately instead of
retrying, since retrying those just wastes time.

**On storing API keys**: prefer `api_key_env` (reads from your `.env`) over
the `api_key` field (stored in plaintext in `providers.json`, which isn't
gitignored by default). The UI form supports both; use `api_key` only for
quick local testing.

## What's new: snapshots, execution, routing, consensus, auth, images

⚠️ **Read the code-execution warning below before enabling the Run tab.**

- **Version snapshots + rollback** — a zip checkpoint of the whole workspace,
  taken automatically before every pipeline run and every auto-fix loop, plus
  a manual "checkpoint now" button. Roll back from the sidebar or
  `python cli.py rollback <id>`. Snapshots live in
  `workspace/<user>/.snapshots/` and never show up in the file list or export.
- **Real code execution + auto-fix** (`executor.py`, Run tab) — runs a shell
  command in the workspace and shows stdout/stderr. Auto-fix mode reruns on
  failure, sending the error and the named file to the coder agent for a fix,
  up to a few attempts. **This executes real commands with the server's own
  OS privileges — there is no sandbox, only a working-directory restriction
  and a timeout.** The code being run was written by an LLM. Only point this
  at your own machine, or better, run the whole server inside a container
  (Docker, firejail, gVisor) so a bad generation can't do damage outside it.
- **Auto-routing** (`router.py`) — pick "auto-route" in the agent strip and
  a router provider (default GLM) classifies each message against every
  registered provider's `description` field to pick the best fit. It's a
  heuristic (one extra classification call), not a guarantee — pick a
  provider directly any time you want certainty.
- **Consensus mode** (`consensus.py`) — pick "consensus (all)" to query
  every registered provider in parallel (or a specific subset via the API)
  and get back all drafts plus one merged answer. Useful for spotting where
  backends disagree.
- **API auth + per-user workspaces** (`auth.py`) — set `PARADOX_API_KEYS` in
  `.env` (format `key1:alice,key2:bob`) to require an `X-API-Key` header and
  give each key its own workspace, files, and chat sessions. Leave it unset
  and the server behaves exactly as before (single "default" workspace, no
  auth). This is a static key list, not a real auth system — put something
  real in front of it before exposing this beyond people you trust. Paste a
  key into the field top-right of the web UI to use it there.
- **Image upload in chat** — the 📎 button attaches an image to your next
  message, wired through to the gpt-4-mini agent (the one described as
  handling images). Claude-proxy and GLM ignore it for now.

## Running with Docker

```bash
cp .env.example .env        # fill in your (rotated) NVIDIA_API_KEY etc.
touch paradox.db            # only needed if PARADOX_AUTH_MODE=accounts
docker compose up --build
```
Open `http://localhost:8000`. `workspace/` and `providers.json` are bind-mounted
from the host so generated files and provider config survive a rebuild.

Without compose:
```bash
docker build -t paradox-ai .
docker run -p 8000:8000 --env-file .env \
  -v $(pwd)/workspace:/app/workspace \
  -v $(pwd)/providers.json:/app/providers.json \
  paradox-ai
```

The container runs as a non-root user (uid 1000). This is worth knowing
about for two reasons: it meaningfully shrinks the blast radius of the
**Run tab / executor.py** (agent-generated shell commands execute inside
the container, not on your host) — though it's still not a real sandbox,
see that module's docstring — and it means bind-mounted host directories
need to be writable by uid 1000, or you'll hit permission errors on write
(`sudo chown -R 1000:1000 workspace providers.json` fixes it).

**I couldn't actually build or run this image** in the environment I built
it in (no Docker daemon, no network access there) — I validated the
Dockerfile/compose file structurally (YAML parses, non-root user, healthcheck)
but haven't confirmed it builds and serves traffic end-to-end. Worth a test
build before you rely on it.

## CI/CD

`.github/workflows/ci.yml` runs on every push/PR to `main`:
1. **Lint + syntax** — `ruff check .` (scoped to real bugs — unused
   imports, undefined names — not style, via `pyproject.toml`) plus a
   `py_compile` pass.
2. **Docker build + smoke test** — builds the image, runs it, waits for
   `/api/meta` to respond, then runs `scripts/smoke_test.py` (checks
   `/api/meta`, `/api/providers`, `/api/workspace/files` come back with
   the expected shape). This is a smoke test, not a real test suite — it
   catches "the container doesn't start" or "a route 500s," nothing more.
3. **Publish** — on push to `main` only, builds and pushes the image to
   `ghcr.io/<your-repo>:latest` using the repo's own `GITHUB_TOKEN` (no
   extra secret needed, but the package visibility defaults to private —
   change that in the repo's package settings if you want it public).

None of this has actually run yet since it only executes on GitHub — first
push will be the real test.

## Accounts, credits, and making yourself the creator

Off by default (`PARADOX_AUTH_MODE=none`, same single-tenant behavior as
before). Turn it on:

```bash
# in .env
PARADOX_AUTH_MODE=accounts
CREATOR_EMAILS=you@example.com    # <-- this is how you become unlimited
```

**To make yourself the creator with unlimited credits**: put your email in
`CREATOR_EMAILS` *before* you sign up — the account gets `is_creator` and
`unlimited_credits` set automatically the moment it's created (via email or
Google). Already signed up before setting it? Run:
```bash
python cli.py grant-unlimited you@example.com
```
Everyone else gets `PARADOX_STARTING_CREDITS` (default 50) and spends
credits per call — 1 for chat, 1-per-provider for consensus, 3 for a
pipeline run, 1 for an auto-fix attempt. This is a flat, coarse v1 model
(see `credits.py`), not real per-token accounting — good enough to stop
runaway usage, not a billing system.

Admin commands:
```bash
python cli.py users                          # list accounts + credit status
python cli.py grant-unlimited <email>         # promote to creator/unlimited
python cli.py add-credits <email> <amount>    # can be negative
```

**Email/password**: standard signup/login, passwords hashed with
PBKDF2-HMAC-SHA256 (390k iterations, per-account salt) — never stored in
plaintext. 5 failed logins locks the account for 15 minutes.

**Google sign-in**: needs your own OAuth credentials —
1. [Google Cloud Console](https://console.cloud.google.com/) → APIs &
   Services → OAuth consent screen → configure it (External is fine for
   testing with your own account).
2. Credentials → Create Credentials → OAuth client ID → Web application.
3. Add an **Authorized redirect URI**: `http://localhost:8000/auth/google/callback`
   (swap the host for your real domain in production).
4. Copy the Client ID and Client Secret into `.env` as `GOOGLE_CLIENT_ID`
   / `GOOGLE_CLIENT_SECRET`.

Both signup methods require accepting the Terms of Service and Privacy
Policy (checkbox for email signup, implied by clicking through for Google —
see both docs below).

## Security posture — what's covered and what isn't

I want to be direct about this rather than oversell it: **there's no such
thing as "hack-proof," and I'm not claiming this is.** What's actually in
place, concretely:

- Passwords: PBKDF2-HMAC-SHA256, salted, never logged or stored plaintext
- Login lockout after 5 failed attempts (15 min), rate limiting on
  signup/login (`ratelimit.py`) to slow down credential stuffing
- Timing-safe password comparison (`secrets.compare_digest`)
- Per-user workspace sandboxing (path traversal guarded in `workspace.py`)
- Security headers (CSP, X-Frame-Options, X-Content-Type-Options,
  Referrer-Policy) via middleware in `server.py`
- Non-root Docker user, containerized code execution (see the Docker
  section above)
- SQL via parameterized queries throughout `db.py` (no string-built SQL)

**What's explicitly NOT covered, so you don't find out the hard way:**
- No HTTPS/TLS — that's your reverse proxy's job (nginx/Caddy/a cloud LB)
- No email verification on signup (an account can be created with an email
  you don't own)
- No 2FA, no session expiry (API keys are long-lived until rotated)
- No CSRF protection (mitigated somewhat by this being a bearer-token API,
  not cookie-based, but worth knowing)
- Rate limiting is in-process memory — doesn't coordinate across multiple
  server instances if you scale out
- The Run tab executes real code with the server's OS privileges — Docker
  containerization helps, but see `executor.py`'s warning
- No independent security audit or penetration test has been done on this

If this is going to face the open internet with real users, get someone
who does security professionally to review it — this is a reasonable
baseline for a small/trusted deployment, not a certified-secure system.

## Terms of Service & Privacy Policy

`TERMS_OF_SERVICE.md` and `PRIVACY_POLICY.md` (served at `/terms` and
`/privacy`, linked in the footer and the signup form) are **templates
written to match what this codebase actually does — not lawyer-reviewed
legal documents.** They're honest about the parts that matter most here:
this app forwards your messages to third-party AI providers, some of which
(the omegatech endpoints) are unverified and unofficial, and their data
handling isn't something this codebase's author can vouch for. Fill in the
bracketed placeholders (your name/contact, retention policy) and have an
actual lawyer review both before real users rely on them — especially if
you're in or serving the EU/UK (GDPR) or California (CCPA/CPRA).

## Project layout

```
paradox_ai/
  config.py       # env-driven settings, no secrets hardcoded
  auth.py         # 3 auth modes: none / apikeys / accounts
  accounts.py     # signup/login business logic (email + Google OAuth)
  db.py           # SQLite: user accounts + credit usage (stdlib sqlite3)
  credits.py      # per-call credit metering, inert outside accounts mode
  ratelimit.py    # in-memory rate limiter (auth endpoints + general use)
  providers.py    # the plugin engine: registry + generic call/retry logic
  providers.json  # editable list of registered AI backends (the "plugins")
  sessions.py     # in-memory chat history per (user, session) key
  router.py       # auto-routing: picks a provider per message
  consensus.py    # queries multiple providers in parallel + merges answers
  pipeline.py     # architect -> coder -> reviewer chain, writes files
  executor.py     # runs commands + auto-fix loop (see safety warning above)
  snapshots.py    # zip checkpoints of a user's workspace + rollback
  workspace.py    # sandboxed, per-user file/zip read-write
  browser.py      # fetch + strip a URL down to readable text
  server.py       # FastAPI app: web UI + all REST routes
  cli.py          # command-line interface: chat/repl/pipeline/exec/users/...
  static/index.html   # tabbed UI: Chat / Editor / Preview / Pipeline / Run
  TERMS_OF_SERVICE.md, PRIVACY_POLICY.md   # templates, see notes above
  workspace/      # generated files land here, one subfolder per user
  paradox.db      # created automatically in accounts mode (SQLite)
  Dockerfile, docker-compose.yml, .dockerignore
  .github/workflows/ci.yml
  scripts/smoke_test.py
```

## Evolving this into a pure API later

`server.py`'s routes (`/api/chat`, `/api/workspace/*`, `/api/browse`) are
already a clean REST surface — the web UI is just one consumer of them.
To ship it as an API product: add auth (an API key header), rate limiting,
and per-user workspace isolation (right now there's a single shared
`workspace/` folder).
