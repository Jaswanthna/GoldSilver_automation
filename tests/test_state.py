import tempfile
import unittest
from pathlib import Path

from gold_silver_agent.state import PriceStateError, load_price_state, prices_changed, save_price_state


class PriceStateTests(unittest.TestCase):
    def test_state_round_trips(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            values = {"gold_24k": "10,000", "silver": "100"}

            save_price_state("goldmeter", values, path)

            self.assertEqual(load_price_state(path), ("goldmeter", values))
            self.assertFalse(path.with_name("state.json.tmp").exists())

    def test_missing_state_is_a_first_run(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIsNone(load_price_state(Path(directory) / "missing.json"))

    def test_corrupt_state_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text("{", encoding="utf-8")

            with self.assertRaisesRegex(PriceStateError, "invalid JSON"):
                load_price_state(path)

    def test_numeric_formatting_differences_are_not_price_changes(self):
        self.assertFalse(prices_changed({"gold": "10,000.00"}, {"gold": "10000"}))
        self.assertTrue(prices_changed({"gold": "10000"}, {"gold": "10,001"}))


if __name__ == "__main__":
    unittest.main()
