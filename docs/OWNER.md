# Owner identity and adding models

Paradox does not guess who you are. You declare it in `.env`, then restart.

## Become owner

```bash
# Option A — secret you paste in the UI Owner key box
PARADOX_OWNER_KEY=pick-a-long-random-string

# Option B — accounts mode, this email becomes owner on signup
PARADOX_AUTH_MODE=accounts
CREATOR_EMAILS=you@email.com
```

Laptop-only shortcut (do not use on a public host):

```bash
PARADOX_ALLOW_LOCAL_PROVIDER_EDIT=1
```

Copy `.env.example` to `.env` first.

## Add Omegatech or any new model

1. Set owner as above and restart.
2. In the UI paste the owner key, then click **+ add model**.
3. Preset **Omegatech HTTP GET** (or NVIDIA / OpenAI / Groq / Custom).
4. Give it any display name you want.
5. For Omegatech, base URL is `https://omegatech-api.dixonomega.tech/api/ai` and path is `/Claude`, `/Gpt-4-mini`, or whatever new route they add.
6. Save. Everyone can use it. Only the owner can register the next one.

CLI on the server machine:

```bash
python cli.py add-provider my-new-model.json
```

The bar under each model name shows the connection kind, for example:

- `HTTP GET proxy · omegatech-api.dixonomega.tech · path /Claude`
- `OpenAI-compatible chat API · integrate.api.nvidia.com · model z-ai/glm-5.2`

## Dangerous tools (off by default)

```bash
PARADOX_ENABLE_EXEC=0
PARADOX_ENABLE_BROWSE=0
```

Set to `1` only if you understand the risk.
