# Paradox AI

*Allen once said: from the deepest depth of darkness comes digital innovations.*

A single console over multiple AI backends, with a shared workspace for generated apps and a plugin registry so new models can be added by name — Omegatech HTTP GET, NVIDIA NIM, OpenAI-compatible hosts, or anything you point at.

**Owner-gated.** Set `PARADOX_OWNER_KEY`, paste it in the UI, then **+ add model**. Everyone can use the model. Only the owner registers the next one. The strip under each name shows the connection kind (`HTTP GET proxy` vs `OpenAI-compatible chat API`) and the host it actually calls.

[Who is the owner / how to add APIs](docs/OWNER.md)

## Before you deploy

1. Put secrets in `.env` only. Copy `.env.example`.
2. Omegatech (`omegatech-api.dixonomega.tech`) is a **third-party, unofficial** proxy — not Anthropic or OpenAI. The UI marks it that way.
3. `PARADOX_ENABLE_EXEC` and `PARADOX_ENABLE_BROWSE` stay **off** on a public host.

## Setup

```bash
cd Paradox-Agentic-ai
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# set NVIDIA_API_KEY and PARADOX_OWNER_KEY
uvicorn server:app --reload --port 8000
```

Open `http://localhost:8000`.

## Fly.io

`Dockerfile` and `fly.toml` both use port **8000**.

```bash
fly secrets set PARADOX_OWNER_KEY=your-long-secret
fly secrets set NVIDIA_API_KEY=your-nvidia-key
fly secrets set PARADOX_ENABLE_EXEC=0 PARADOX_ENABLE_BROWSE=0
fly deploy
```

Attach a volume if you need `providers.json` and workspace files to survive machine sleep.

## Architecture

| Piece | Role |
|---|---|
| `server.py` | FastAPI app, owner gates, feature flags |
| `providers.py` | Registry + connection labels |
| `owner.py` | How you become owner |
| `workspace.py` | Per-user sandbox + zip limits |
| `browser.py` | Public-URL fetch with SSRF block |

## License

See repository files. Product of Paradox Tech.
