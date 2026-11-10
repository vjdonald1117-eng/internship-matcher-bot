import os
from pathlib import Path
from typing import List
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
AUTH_DIR = BASE_DIR / "auth"

DATA_DIR.mkdir(parents=True, exist_ok=True)
AUTH_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    # Your Discord Webhook URL is baked in as the default so it works automatically
    DISCORD_WEBHOOK_URL: str = os.getenv(
        "DISCORD_WEBHOOK_URL",
        "https://discord.com/api/webhooks/1569526445963747348/rTaX8H3QrZjcTm2_kdThUX68eedERQii2T-0JfefTy5yiY_MjFeHwWDtLWsQFzBBiesn",
    )
    SIMILARITY_THRESHOLD: float = float(os.getenv("SIMILARITY_THRESHOLD", "0.45"))

    # Automatically catered to your 3 keyphrases
    SEARCH_KEYWORDS: List[str] = [
        "Software Engineering Intern",
        "Software Development Intern",
        "AI Engineering Intern",
    ]
    SEARCH_LOCATIONS: List[str] = ["United States"]
    MAX_JOBS_PER_PLATFORM: int = int(os.getenv("MAX_JOBS_PER_PLATFORM", "15"))

    HANDSHAKE_BASE_URL: str = os.getenv(
        "HANDSHAKE_BASE_URL", "https://app.joinhandshake.com"
    )
    HANDSHAKE_STATE_PATH: Path = AUTH_DIR / "handshake_state.json"

    DB_PATH: Path = DATA_DIR / "jobs.db"
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"


settings = Config()