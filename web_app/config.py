import os
import logging
from pathlib import Path

# Load .env from the project root when running locally (no-op in Docker where
# vars are injected by compose).
_env_path = Path(__file__).parent.parent / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./architect.db")
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
CORS_ORIGINS: list[str] = os.getenv("CORS_ORIGINS", "*").split(",")
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")


def configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
