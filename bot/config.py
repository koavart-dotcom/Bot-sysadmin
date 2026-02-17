import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    ADMIN_CHAT_ID: int = field(
        default_factory=lambda: int(os.getenv("ADMIN_CHAT_ID", "0"))
    )
    SENIOR_ADMIN_IDS: list[int] = field(default_factory=lambda: [
        int(x.strip())
        for x in os.getenv("SENIOR_ADMIN_IDS", "").split(",")
        if x.strip()
    ])
    DATABASE_URL: str = field(
        default_factory=lambda: os.getenv(
            "DATABASE_URL", "sqlite+aiosqlite:///data/bot.db"
        )
    )
    LOG_LEVEL: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


settings = Settings()
