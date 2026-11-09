import contextlib
import io
import unittest
from unittest.mock import patch

from gold_silver_agent.config import Settings
from gold_silver_agent.rates import RateQuote
from main import run_once


class ScheduledMessageTests(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(
            goldmeter_url="https://goldmeter.in/",
            telegram_bot_token="123456:example-token",
            telegram_chat_id="123456789",
            interval_hours=3,
        )
        self.quote = RateQuote(
            gold_24k="10,000",
            gold_22k="9,200",
            gold_18k="7,500",
            silver="100",
        )
        self.current_values = {
            "gold_24k": self.quote.gold_24k,
            "gold_22k": self.quote.gold_22k,
            "gold_18k": self.quote.gold_18k,
            "silver": self.quote.silver,
        }

    @patch("main.save_price_state")
    @patch("main.send_message")
    @patch("main.load_price_state", return_value=None)
    @patch("main.fetch_rates")
    def test_first_run_sends_rates_and_saves_baseline(self, fetch_rates, load_state, send, save_state):
        fetch_rates.return_value = self.quote

        run_once(self.settings)

        send.assert_called_once_with(self.settings, self.quote.message())
        save_state.assert_called_once_with(self.settings.goldmeter_url, self.current_values)

    @patch("main.save_price_state")
    @patch("main.send_message")
    @patch("main.load_price_state")
    @patch("main.fetch_rates")
    def test_unchanged_prices_send_no_change_message(self, fetch_rates, load_state, send, save_state):
        fetch_rates.return_value = self.quote
        load_state.return_value = (self.settings.goldmeter_url, self.current_values.copy())

        run_once(self.settings)

        send.assert_called_once_with(self.settings, "No change in the price")
        save_state.assert_called_once_with(self.settings.goldmeter_url, self.current_values)

    @patch("main.save_price_state")
    @patch("main.send_message")
    @patch("main.load_price_state")
    @patch("main.fetch_rates")
    def test_price_change_sends_full_rates(self, fetch_rates, load_state, send, save_state):
        fetch_rates.return_value = self.quote
        previous_values = self.current_values.copy()
        previous_values["silver"] = "99"
        load_state.return_value = (self.settings.goldmeter_url, previous_values)

        run_once(self.settings)

        send.assert_called_once_with(self.settings, self.quote.message())
        save_state.assert_called_once_with(self.settings.goldmeter_url, self.current_values)

    @patch("main.save_price_state")
    @patch("main.send_message")
    @patch("main.load_price_state", return_value=None)
    @patch("main.fetch_rates")
    def test_dry_run_does_not_send_or_save_baseline(self, fetch_rates, load_state, send, save_state):
        fetch_rates.return_value = self.quote
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            run_once(self.settings, dry_run=True)

        self.assertIn(self.quote.message(), output.getvalue())
        send.assert_not_called()
        save_state.assert_not_called()

    @patch("main.save_price_state")
    @patch("main.send_message", side_effect=RuntimeError("Telegram unavailable"))
    @patch("main.load_price_state", return_value=None)
    @patch("main.fetch_rates")
    def test_send_failure_does_not_update_baseline(self, fetch_rates, load_state, send, save_state):
        fetch_rates.return_value = self.quote

        with self.assertRaisesRegex(RuntimeError, "Telegram unavailable"):
            run_once(self.settings)

        save_state.assert_not_called()


if __name__ == "__main__":
    unittest.main()
