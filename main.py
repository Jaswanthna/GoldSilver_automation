import argparse
import json
import logging
import time

from gold_silver_agent.config import Settings
from gold_silver_agent.rates import fetch_rates
from gold_silver_agent.source import fetch_message_data, load_message_source
from gold_silver_agent.state import load_price_state, prices_changed, save_price_state
from gold_silver_agent.telegram import get_chat_ids, send_message


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_once(settings: Settings, dry_run: bool = False) -> None:
    if settings.message_source_config:
        source = load_message_source(settings.message_source_config)
        message, current_values = fetch_message_data(source)
        source_id = json.dumps(
            {
                "url": source.url,
                "format": source.response_format,
                "fields": source.fields,
                "compare_fields": source.compare_fields,
            },
            sort_keys=True,
        )
    else:
        quote = fetch_rates(settings.goldmeter_url)
        message = quote.message()
        current_values = {
            "gold_24k": quote.gold_24k,
            "gold_22k": quote.gold_22k,
            "gold_18k": quote.gold_18k,
            "silver": quote.silver,
        }
        source_id = settings.goldmeter_url

    previous_state = load_price_state()
    unchanged = (
        previous_state is not None
        and previous_state[0] == source_id
        and not prices_changed(previous_state[1], current_values)
    )
    if unchanged:
        message = "No change in the price"

    if dry_run:
        print("DRY RUN - message not sent")
        print(message)
        return
    send_message(settings, message)
    save_price_state(source_id, current_values)
    if unchanged:
        logging.info("Prices are unchanged; no-change message sent to the configured Telegram chat")
    else:
        logging.info("Current rates sent to the configured Telegram chat")


def main() -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Send configured data to a Telegram chat")
    parser.add_argument("--once", action="store_true", help="fetch and send once, then exit")
    parser.add_argument("--dry-run", action="store_true", help="fetch rates and print the message without sending")
    parser.add_argument("--show-chat-id", action="store_true", help="list Telegram chat IDs that have messaged your bot")
    args = parser.parse_args()

    if args.show_chat_id:
        get_chat_ids(settings)
        return 0

    if args.once or args.dry_run:
        run_once(settings, dry_run=args.dry_run)
        return 0

    logging.info("Starting scheduled runs every %s hour(s)", settings.interval_hours)
    while True:
        try:
            run_once(settings)
        except Exception:
            logging.exception("Rate check failed; no message was sent")
        time.sleep(settings.interval_hours * 60 * 60)


if __name__ == "__main__":
    raise SystemExit(main())
