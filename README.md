<div align="center">

# Paradox AI

**Paradox Tech** · multi-model agentic console

*From the deepest depth of darkness comes digital innovations.*

[Owner guide](docs/OWNER.md) · [Profile](https://github.com/Paradoxdreamer)

`Python` · `FastAPI` · `Docker` · `Fly.io`

</div>

---

One workspace. Many backends. You name the model; Paradox routes the work.

Plug in **Omegatech HTTP GET**, **NVIDIA NIM**, **OpenAI**, **Groq**, or any host that speaks those shapes. The bar under each name states the connection — `HTTP GET proxy · host · path` or `OpenAI-compatible chat API · model` — so nobody guesses what they are talking to.

## What it is

| Surface | What it does |
|---|---|
| Chat | Stream against one provider, auto-route, or consensus |
| Workspace | Sandboxed files, zip import/export, snapshots |
| Pipeline | Architect → coder → reviewer into the workspace |
| Registry | Owner adds a model by **name** + URL. Everyone else can use it |

House colors in the UI: navy `#0A2540`, teal `#00D4C8`. Looping **PARADOX TECH** ticker on the console.

## Become owner, then add APIs

Paradox does not infer who you are.

```bash
cp .env.example .env
# Option A
PARADOX_OWNER_KEY=a-long-random-secret
# Option B (accounts mode)
PARADOX_AUTH_MODE=accounts
CREATOR_EMAILS=you@email.com
```

Restart. Paste the owner key in the UI. **+ add model** → preset (Omegatech / NVIDIA / OpenAI / Groq) → display name of your choosing → save.

Example Omegatech:

- Base `https://omegatech-api.dixonomega.tech/api/ai`
- Path `/Claude` or whatever new route they ship
- Kind `http_get`

Full walkthrough: [docs/OWNER.md](docs/OWNER.md)

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

## Rules that keep it professional

1. Secrets live in `.env` / Fly secrets. Never in git.
2. Omegatech is a **third-party, unofficial** proxy. The UI labels it that way.
3. `PARADOX_ENABLE_EXEC` and `PARADOX_ENABLE_BROWSE` stay off on a public URL.

## Layout

```
server.py       FastAPI, owner gates, feature flags
providers.py    Registry + connection labels
owner.py        How identity is decided
workspace.py    Per-user sandbox, zip limits
browser.py      Public fetch, private IPs blocked
static/         Navy / teal console + ticker
docs/OWNER.md   Add a model without touching code
```

---

<div align="center">

**Paradox Tech**

Allen once said: from the deepest depth of darkness comes digital innovations.

</div>
