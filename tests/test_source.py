import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from gold_silver_agent.config import Settings
from gold_silver_agent.source import (
    MessageSourceError,
    fetch_message,
    fetch_message_data,
    load_message_source,
)
from main import run_once


class MessageSourceTests(unittest.TestCase):
    def load_config(self, config):
        temporary = tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False)
        with temporary:
            json.dump(config, temporary)
        self.addCleanup(Path(temporary.name).unlink, missing_ok=True)
        return load_message_source(temporary.name)

    def test_fetches_json_fields_and_renders_message_template(self):
        source = self.load_config(
            {
                "url": "https://data.example.com/prices",
                "format": "json",
                "fields": {
                    "price": {"path": "/data/price"},
                    "currency": {"path": "/data/currency"},
                    "updated_at": {"path": "/data/updated_at"},
                },
                "compare_fields": ["price"],
                "template": "{{currency}} {{price}}",
            }
        )
        response = Mock(
            status_code=200,
            url=source.url,
            text='{"data":{"price":42,"currency":"USD","updated_at":"now"}}',
            headers={"Content-Type": "application/json"},
        )
        with patch("gold_silver_agent.source.requests.get", return_value=response) as get:
            message, comparison_values = fetch_message_data(source)

        self.assertEqual(message, "USD 42")
        self.assertEqual(comparison_values, {"price": "42"})
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_extracts_html_using_css_selector_and_pattern(self):
        source = self.load_config(
            {
                "url": "https://data.example.com/weather",
                "format": "html",
                "fields": {"temperature": {"selector": "#temperature", "pattern": r"(\d+)"}},
                "template": "Temperature: {{temperature}} C",
            }
        )
        response = Mock(
            status_code=200,
            url=source.url,
            text='<p id="temperature">28 degrees</p>',
            headers={"Content-Type": "text/html; charset=utf-8"},
        )
        with patch("gold_silver_agent.source.requests.get", return_value=response):
            self.assertEqual(fetch_message(source), "Temperature: 28 C")

    def test_rejects_redirect_without_following_it(self):
        source = self.load_config(
            {
                "url": "https://data.example.com/prices",
                "format": "json",
                "fields": {"price": {"path": "/price"}},
                "template": "Price {{price}}",
            }
        )
        response = Mock(status_code=302, url="https://elsewhere.example/prices")
        with patch("gold_silver_agent.source.requests.get", return_value=response) as get:
            with self.assertRaisesRegex(MessageSourceError, "redirected"):
                fetch_message(source)
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_rejects_missing_field_in_source_response(self):
        source = self.load_config(
            {
                "url": "https://data.example.com/prices",
                "format": "json",
                "fields": {"price": {"path": "/price"}},
                "template": "Price {{price}}",
            }
        )
        response = Mock(
            status_code=200,
            url=source.url,
            text="{}",
            headers={"Content-Type": "application/json"},
        )
        with patch("gold_silver_agent.source.requests.get", return_value=response):
            with self.assertRaisesRegex(MessageSourceError, "configured JSON field"):
                fetch_message(source)

    def test_rejects_template_placeholders_without_a_field(self):
        with self.assertRaisesRegex(MessageSourceError, "undefined fields"):
            self.load_config(
                {
                    "url": "https://data.example.com/prices",
                    "format": "json",
                    "fields": {"price": {"path": "/price"}},
                    "template": "Price {{missing}}",
                }
            )

    def test_run_once_uses_configured_source_for_dry_run(self):
        settings = Settings(
            goldmeter_url="https://goldmeter.in/",
            telegram_bot_token="",
            telegram_chat_id="",
            interval_hours=24,
            message_source_config="message-source.json",
        )
        source = self.load_config(
            {
                "url": "https://data.example.com/prices",
                "format": "json",
                "fields": {"price": {"path": "/price"}},
                "template": "Price {{price}}",
            }
        )
        output = io.StringIO()
        with patch("main.load_message_source", return_value=source), patch(
            "main.fetch_message_data", return_value=("Price 42", {"price": "42"})
        ) as fetch, patch("main.load_price_state", return_value=None), contextlib.redirect_stdout(output):
            run_once(settings, dry_run=True)

        self.assertIn("Price 42", output.getvalue())
        fetch.assert_called_once_with(source)


if __name__ == "__main__":
    unittest.main()
