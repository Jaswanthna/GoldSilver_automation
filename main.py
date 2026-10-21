import argparse
import logging
import time

from gold_silver_agent.config import Settings
from gold_silver_agent.rates import fetch_rates
from gold_silver_agent.telegram import get_chat_ids, send_rate_message


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def run_once(settings: Settings, dry_run: bool = False) -> None:
    quote = fetch_rates(settings.goldmeter_url)
    if dry_run:
        print("DRY RUN - message not sent")
        print(quote.message())
        return
    send_rate_message(settings, quote)
    logging.info("Rate message sent to the configured Telegram chat")


def main() -> int:
    settings = Settings.from_env()
    parser = argparse.ArgumentParser(description="Send Goldmeter gold and silver rates to Telegram")
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
