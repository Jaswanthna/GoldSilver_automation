import requests

from .config import Settings
from .rates import RateQuote


def _telegram_request(settings: Settings, method: str, payload: dict | None = None) -> dict:
    endpoint = f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}"
    try:
        if payload is None:
            response = requests.get(endpoint, timeout=20)
        else:
            response = requests.post(endpoint, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
    except requests.RequestException:
        raise RuntimeError("Telegram Bot API request failed; check the bot token and network") from None
    except ValueError:
        raise RuntimeError("Telegram Bot API returned invalid JSON") from None
    if not result.get("ok"):
        raise RuntimeError("Telegram rejected the request: " + result.get("description", "unknown error"))
    return result


def get_chat_ids(settings: Settings) -> None:
    if not settings.telegram_bot_token:
        raise ValueError("Set TELEGRAM_BOT_TOKEN in .env first")
    result = _telegram_request(settings, "getUpdates")
    chats = {}
    for update in result.get("result", []):
        message = update.get("message", {})
        chat = message.get("chat", {})
        if "id" in chat:
            chats[chat["id"]] = chat
    if not chats:
        print("No chat found. Open your bot in Telegram, send /start, then run this command again.")
        return
    for chat_id, chat in chats.items():
        label = chat.get("username") or chat.get("first_name") or chat.get("type", "chat")
        print(f"TELEGRAM_CHAT_ID={chat_id} ({label})")


def send_rate_message(settings: Settings, quote: RateQuote) -> None:
    settings.validate_telegram()
    _telegram_request(
        settings,
        "sendMessage",
        {"chat_id": settings.telegram_chat_id, "text": quote.message()},
    )