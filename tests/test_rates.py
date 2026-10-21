import unittest
from unittest.mock import Mock, patch

import requests

from gold_silver_agent.rates import RateSourceError, extract_rates, fetch_rates


class RateParsingTests(unittest.TestCase):
    def test_extracts_explicitly_labeled_currency_values(self):
        html = """
        <html><body>
                    <p>Live India prices are ₹ 9,999.50 per gram for 24K (99.9%),
                    ₹ 9,166 per gram for 22K (91.6%), and ₹ 7,499 per gram for 18K (75%).
                    Silver rate is Rs. 101 per gram. Prices updated today.</p>
        </body></html>
        """
        quote = extract_rates(html)
        self.assertEqual(quote.gold_24k, "9,999.50")
        self.assertEqual(quote.gold_22k, "9,166")
        self.assertEqual(quote.gold_18k, "7,499")
        self.assertEqual(quote.silver, "101")
        self.assertEqual(
            quote.message(),
            "Gold (24K): ₹9,999.50 per gram\n"
            "Gold (22K): ₹9,166 per gram\n"
            "Gold (18K): ₹7,499 per gram\n"
            "Silver: ₹101 per gram",
        )

    def test_rejects_page_missing_any_requested_rate(self):
        html = """<p>Live India prices are ₹10 per gram for 24K, ₹9 per gram for 22K.
        Silver rate is ₹1 per gram. Prices updated today.</p>"""
        with self.assertRaisesRegex(RateSourceError, "all four rates"):
            extract_rates(html)

    def test_does_not_use_rates_from_city_or_history_sections(self):
        html = """
        <p>Gold Rates Across Major Indian Cities (22K per gram): Ahmedabad: ₹ 13,540</p>
        <p>Gold Rate in India for Last 10 Days (1 gram) Date 24K ₹ 14,766</p>
        """
        with self.assertRaisesRegex(RateSourceError, "all four rates"):
            extract_rates(html)

        def test_uses_dedicated_rates_table_when_summary_is_unavailable(self):
                html = """
                <table>
                    <tr><td>Gold 24K</td><td>99.9%</td><td>₹</td><td>14,766</td><td>₹ 1,18,128</td></tr>
                    <tr><td>Gold 22K</td><td>91.6%</td><td>₹</td><td>13,535</td><td>₹ 1,08,280</td></tr>
                    <tr><td>Gold 18K</td><td>75.0%</td><td>₹</td><td>11,075</td><td>₹ 88,600</td></tr>
                    <tr><td>Silver</td><td>99.9%</td><td>₹</td><td>230</td><td>₹ 1,840</td></tr>
                </table>
                <table><tr><td>Gold Rates</td><td>24K</td><td>₹ 100</td></tr></table>
                """
                quote = extract_rates(html)
                self.assertEqual(quote.gold_24k, "14,766")
                self.assertEqual(quote.gold_22k, "13,535")
                self.assertEqual(quote.gold_18k, "11,075")
                self.assertEqual(quote.silver, "230")

    @patch("gold_silver_agent.rates.requests.get")
    def test_rejects_redirect_without_following_it(self, get):
        response = Mock()
        response.status_code = 302
        get.return_value = response

        with self.assertRaisesRegex(RateSourceError, "redirected"):
            fetch_rates("https://goldmeter.in/")

        get.assert_called_once()
        self.assertFalse(get.call_args.kwargs["allow_redirects"])

    def test_rejects_non_goldmeter_host_before_request(self):
        with patch("gold_silver_agent.rates.requests.get") as get:
            with self.assertRaisesRegex(RateSourceError, "exact goldmeter.in host"):
                fetch_rates("https://example.com/")
        get.assert_not_called()


if __name__ == "__main__":
    unittest.main()
