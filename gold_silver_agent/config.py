from dataclasses import dataclass
import os
from pathlib import Path
import re

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    goldmeter_url: str
    telegram_bot_token: str
    telegram_chat_id: str
    interval_hours: int

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")
        try:
            interval_hours = int(os.getenv("INTERVAL_HOURS", "3"))
        except ValueError as exc:
            raise ValueError("INTERVAL_HOURS must be a positive integer") from exc
        if interval_hours < 1:
            raise ValueError("INTERVAL_HOURS must be a positive integer")

        return cls(
            goldmeter_url=os.getenv("GOLDMETER_URL", "https://goldmeter.in/"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", "").strip(),
            telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID", "").strip(),
            interval_hours=interval_hours,
        )

    def validate_telegram(self) -> None:
        missing = []
        if not self.telegram_bot_token:
            missing.append("TELEGRAM_BOT_TOKEN")
        if not self.telegram_chat_id:
            missing.append("TELEGRAM_CHAT_ID")
        if missing:
            raise ValueError("Missing Telegram settings: " + ", ".join(missing))
        if not re.fullmatch(r"-?\d+", self.telegram_chat_id):
            raise ValueError("TELEGRAM_CHAT_ID must be a numeric Telegram chat ID")
