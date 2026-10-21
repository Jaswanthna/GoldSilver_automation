import unittest
from unittest.mock import Mock, patch

import requests

from gold_silver_agent.config import Settings
from gold_silver_agent.rates import RateQuote
from gold_silver_agent.telegram import send_rate_message


class TelegramSenderTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            goldmeter_url="https://goldmeter.in/",
            telegram_bot_token="123456:example-token",
            telegram_chat_id="123456789",
            interval_hours=24,
        )
        self.quote = RateQuote(gold_24k="9,999", gold_22k="9,166", gold_18k="7,499", silver="101")

    @patch("gold_silver_agent.telegram.requests.post")
    def test_sends_rate_text_to_configured_telegram_chat(self, post):
        response = Mock()
        response.json.return_value = {"ok": True, "result": {"message_id": 1}}
        post.return_value = response

        send_rate_message(self.settings, self.quote)

        post.assert_called_once_with(
            "https://api.telegram.org/bot123456:example-token/sendMessage",
            json={
                "chat_id": "123456789",
                "text": (
                    "Gold (24K): ₹9,999 per gram\n"
                    "Gold (22K): ₹9,166 per gram\n"
                    "Gold (18K): ₹7,499 per gram\n"
                    "Silver: ₹101 per gram"
                ),
            },
            timeout=20,
        )
        response.raise_for_status.assert_called_once()

    @patch("gold_silver_agent.telegram.requests.post", side_effect=requests.Timeout("request timed out"))
    def test_does_not_include_bot_token_in_request_error(self, post):
        with self.assertRaises(RuntimeError) as raised:
            send_rate_message(self.settings, self.quote)

        self.assertNotIn(self.settings.telegram_bot_token, str(raised.exception))

    def test_requires_numeric_chat_id(self):
        settings = Settings(
            goldmeter_url="https://goldmeter.in/",
            telegram_bot_token="123456:example-token",
            telegram_chat_id="not-a-chat-id",
            interval_hours=24,
        )
        with self.assertRaisesRegex(ValueError, "numeric Telegram chat ID"):
            settings.validate_telegram()


if __name__ == "__main__":
    unittest.main()