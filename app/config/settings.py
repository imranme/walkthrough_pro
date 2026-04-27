import os
import sys
from pathlib import Path
from dotenv import load_dotenv

_HERE = Path(__file__).resolve()

# 1. Find the directory that contains `.env` (the true project root)
_PROJECT_ROOT = _HERE.parent
for _ in range(6):
    if (_PROJECT_ROOT / ".env").exists():
        break
    _PROJECT_ROOT = _PROJECT_ROOT.parent
else:
    # Fallback: use the folder two levels above this file (app/)
    _PROJECT_ROOT = _HERE.parent.parent.parent

# 2. The `app/` dir (one level below project root) holds common/ components/ config/
_APP_DIR = _HERE.parent.parent   # app/config/ -> app/config -> app/

# 3. Make sure `app/` is on sys.path so sibling packages resolve
for _p in [str(_APP_DIR), str(_PROJECT_ROOT)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# 4. Load .env from project root
_ENV_PATH = _PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=_ENV_PATH)


class Settings:
    """Central configuration loaded from environment variables."""

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    OPENAI_MAX_TOKENS: int = int(os.getenv("OPENAI_MAX_TOKENS", "2048"))
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))

    # App
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    APP_NAME: str = "T-TESS AI Coaching Observer"

    # T-TESS rating scale (numeric)
    RATING_MAX: float = 4.0

    def validate(self) -> None:
        """Raise ValueError if any required setting is missing."""
        if not self.OPENAI_API_KEY:
            raise ValueError(
                "OPENAI_API_KEY is not set.\n"
                f"Expected .env at: {_ENV_PATH}\n"
                "Please add OPENAI_API_KEY=sk-... to that file."
            )


settings = Settings()