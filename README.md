<div align="center">

# Paradox Agentic AI

**Paradox Tech** · multi-model agentic console

*From the deepest depth of darkness comes digital innovations.*

[Owner guide](docs/OWNER.md) · [Profile](https://github.com/Paradoxdreamer)

`Python` · `FastAPI` · `Docker` · `Fly.io` · `Vercel`

</div>

---

One workspace. Many backends. You name the model; Paradox routes the work.

Plug in **Omegatech HTTP GET**, **NVIDIA NIM**, **OpenAI**, **Groq**, or any host that speaks those shapes. The bar under each name states the connection — `HTTP GET proxy · host · path` or `OpenAI-compatible chat API · model` — so nobody guesses what they are talking to.

## What it is

| Surface | What it does |
|---------|--------------|
| **Chat** | Stream against one provider, auto-route, or consensus |
| **Workspace** | Sandboxed files, zip import/export, snapshots |
| **Pipeline** | Architect → coder → reviewer into the workspace |
| **Reach** | Internet eyes: web, RSS, YouTube, GitHub, V2EX, Twitter, Reddit |
| **Registry** | Owner adds a model by **name** + URL. Everyone else can use it |

House colors: navy `#0A2540`, teal `#00D4C8`. Looping **PARADOX TECH** ticker on the console.

## How to activate the agent

### End users (chat right away)

1. Open the deployed console (or [http://localhost:8000](http://localhost:8000) if you run it yourself).
2. **Sign in** if the host uses accounts mode:
   - Top bar → log in / sign up (email + password, or Google when enabled).
   - Your session API key is stored in the browser; you do not paste it manually for normal chat.
3. **Pick a model** in the agent strip under the brand (Omegatech, NVIDIA, OpenAI, Groq, or whatever the owner registered).
4. Type in **Chat** and press **Enter** (Shift+Enter for a new line). The agent streams a reply.
5. Optional tabs:
   - **Editor / Preview** — edit and open workspace files
   - **Pipeline** — multi-step build task
   - **Reach** — fetch a public URL, search, V2EX, tweet, Reddit post
   - **Run** — only if the host turned execution on

If no models appear, the **owner** has not registered any yet (see below).

### Host / owner (unlock the registry)

Paradox does not guess who owns the instance. You choose one of these:

```bash
cp .env.example .env

# Option A — secret you paste in the UI when adding models
PARADOX_OWNER_KEY=a-long-random-secret

# Option B — accounts mode: this email is owner after signup
PARADOX_AUTH_MODE=accounts
CREATOR_EMAILS=you@email.com
```

Then:

1. Restart the server (or set the same vars as secrets on Fly / Vercel).
2. Open the console → paste the **owner key** where the UI asks (or sign up with a creator email).
3. Click **+ add model** → choose a preset (Omegatech / NVIDIA / OpenAI / Groq / Custom).
4. Fill base URL / model / API key as needed → **Save**.
5. Everyone on that host can now select that model and chat.

Example Omegatech:

| Field | Example |
|-------|---------|
| Kind | `http_get` |
| Base URL | `https://omegatech-api.dixonomega.tech/api/ai` |
| Path | `/Claude` (or any route they ship) |

Full walkthrough: [docs/OWNER.md](docs/OWNER.md)

### Quick local activate

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: PARADOX_OWNER_KEY=... and any provider API keys
uvicorn server:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000) → owner key → **+ add model** → Chat.

Laptop-only shortcut (never on a public host):

```bash
PARADOX_ALLOW_LOCAL_PROVIDER_EDIT=1
```

## Run locally

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # NVIDIA_API_KEY + PARADOX_OWNER_KEY
uvicorn server:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## Fly.io

Port is **8000** in both `Dockerfile` and `fly.toml`.

```bash
fly secrets set PARADOX_OWNER_KEY=your-long-secret
fly secrets set NVIDIA_API_KEY=your-nvidia-key
fly secrets set PARADOX_ENABLE_EXEC=0 PARADOX_ENABLE_BROWSE=0
fly deploy
```

Attach a volume if `providers.json` and workspace files must survive machine sleep.

## Vercel

`pyproject.toml` declares `[project]` and `[tool.vercel] entrypoint = "server:app"`. Set the same env vars as secrets in the Vercel project. Note: serverless is a poor fit for long streams and local workspace files; prefer Fly for production agent use.

## Rules that keep it professional

1. Secrets live in `.env` / platform secrets. Never in git.
2. Omegatech is a **third-party, unofficial** proxy. The UI labels it that way.
3. `PARADOX_ENABLE_EXEC` and `PARADOX_ENABLE_BROWSE` stay off on a public URL.

## Layout

```
server.py       FastAPI, owner gates, feature flags
providers.py    Registry + connection labels
owner.py        How identity is decided
reach.py        Public internet channels (SSRF-guarded)
vault.py        Owner cookie store for tier-1 social
workspace.py    Per-user sandbox, zip limits
browser.py      Public fetch, private IPs blocked
static/         Navy / teal console + ticker + Reach/vault UI
docs/OWNER.md   Add a model without touching code
```

---

<div align="center">

**Paradox Tech**  
*From the deepest depth of darkness comes digital innovations.*

</div>
