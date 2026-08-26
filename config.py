"""
Paradox AI - configuration

All secrets are read from environment variables (or a local .env file via
python-dotenv). Nothing sensitive is hardcoded.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
GLM_MODEL = os.getenv("GLM_MODEL", "z-ai/glm-5.2")

OMEGA_BASE_URL = os.getenv("OMEGA_BASE_URL", "https://omegatech-api.dixonomega.tech/api/ai")
OMEGA_CLAUDE_PATH = os.getenv("OMEGA_CLAUDE_PATH", "/Claude")
OMEGA_GPT4MINI_PATH = os.getenv("OMEGA_GPT4MINI_PATH", "/Gpt-4-mini")

WORKSPACE_DIR = Path(os.getenv("PARADOX_WORKSPACE", str(Path(__file__).parent / "workspace")))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

APP_NAME = "Paradox AI"
APP_TAGLINE = "Allen once said: from the deepest depth of darkness comes digital innovations."

REQUEST_TIMEOUT = int(os.getenv("PARADOX_REQUEST_TIMEOUT", "60"))

AUTH_MODE = os.getenv("PARADOX_AUTH_MODE", "none")
CREATOR_EMAILS = [e.strip() for e in os.getenv("CREATOR_EMAILS", "").split(",") if e.strip()]
STARTING_CREDITS = int(os.getenv("PARADOX_STARTING_CREDITS", "50"))

# Owner identity: any of these makes you the person who can add/remove
# providers for everyone.
#   PARADOX_OWNER_KEY   — secret you type in the UI / send as X-Owner-Key
#   CREATOR_EMAILS      — those accounts become owner on signup
#   PARADOX_ALLOW_LOCAL_PROVIDER_EDIT=1 — local single-user convenience
OWNER_KEY = os.getenv("PARADOX_OWNER_KEY", "").strip()
ALLOW_LOCAL_PROVIDER_EDIT = _flag("PARADOX_ALLOW_LOCAL_PROVIDER_EDIT", "0")

ENABLE_EXEC = _flag("PARADOX_ENABLE_EXEC", "0")
ENABLE_BROWSE = _flag("PARADOX_ENABLE_BROWSE", "0")

_CORS = os.getenv("PARADOX_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000")
CORS_ORIGINS = [o.strip() for o in _CORS.split(",") if o.strip()]

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_BASE = os.getenv("GOOGLE_REDIRECT_BASE", "http://localhost:8000")
