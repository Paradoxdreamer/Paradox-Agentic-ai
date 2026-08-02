"""
Paradox AI - configuration

All secrets are read from environment variables (or a local .env file via
python-dotenv). Nothing sensitive is hardcoded here or anywhere else in the
project. Copy .env.example to .env and fill in your own keys before running.
"""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv is optional; env vars can also be set directly on the system
    pass

# --- NVIDIA NIM (OpenAI-compatible) endpoint, used for GLM-5.2 ---
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_BASE_URL = os.getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
GLM_MODEL = os.getenv("GLM_MODEL", "z-ai/glm-5.2")

# --- Third-party "omegatech" endpoints ---
# NOTE: these are NOT official Anthropic or OpenAI APIs. They are an
# unverified third-party service. Treat responses defensively (shape/
# reliability/uptime are unknown) and don't assume they're maintained long-term.
OMEGA_BASE_URL = os.getenv("OMEGA_BASE_URL", "https://omegatech-api.dixonomega.tech/api/ai")
OMEGA_CLAUDE_PATH = os.getenv("OMEGA_CLAUDE_PATH", "/Claude")
OMEGA_GPT4MINI_PATH = os.getenv("OMEGA_GPT4MINI_PATH", "/Gpt-4-mini")

# --- Workspace (files, zips, generated app output live here) ---
WORKSPACE_DIR = Path(os.getenv("PARADOX_WORKSPACE", str(Path(__file__).parent / "workspace")))
WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

# --- App metadata ---
APP_NAME = "Paradox AI"
APP_TAGLINE = "Allen once said: from the deepest depth of darkness comes digital innovations."

# --- Networking ---
REQUEST_TIMEOUT = int(os.getenv("PARADOX_REQUEST_TIMEOUT", "60"))

# --- Accounts (optional, off by default -- see auth.py for the 3 modes) ---
AUTH_MODE = os.getenv("PARADOX_AUTH_MODE", "none")  # "none" | "apikeys" | "accounts"
CREATOR_EMAILS = [e.strip() for e in os.getenv("CREATOR_EMAILS", "").split(",") if e.strip()]
STARTING_CREDITS = int(os.getenv("PARADOX_STARTING_CREDITS", "50"))

# --- Google OAuth (only needed if you want "Sign in with Google") ---
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_BASE = os.getenv("GOOGLE_REDIRECT_BASE", "http://localhost:8000")
