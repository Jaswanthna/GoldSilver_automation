from dataclasses import dataclass
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests


class RateSourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class RateQuote:
    gold_24k: str
    gold_22k: str
    gold_18k: str
    silver: str

    def message(self) -> str:
        return (
            f"Gold (24K): ₹{self.gold_24k} per gram\n"
            f"Gold (22K): ₹{self.gold_22k} per gram\n"
            f"Gold (18K): ₹{self.gold_18k} per gram\n"
            f"Silver: ₹{self.silver} per gram"
        )


_MONEY = re.compile(r"(?:₹|Rs\.?|INR)\s*([\d][\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)
_SUMMARY_GOLD = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([\d][\d,]*(?:\.\d{1,2})?)\s*per\s+gram\s+for\s+(24|22|18)\s*k\b",
    re.IGNORECASE,
)


def _summary_rates(text: str) -> dict[str, str] | None:
    summary_start = re.search(r"\bLive India prices are\b", text, re.IGNORECASE)
    if not summary_start:
        return None
    summary_end = re.search(r"\bPrices updated\b", text[summary_start.end() :], re.IGNORECASE)
    if not summary_end:
        return None
    summary = text[summary_start.end() : summary_start.end() + summary_end.start()]

    rates = {}
    for match in _SUMMARY_GOLD.finditer(summary):
        rates[f"{match.group(2)}K"] = match.group(1)
    silver_match = re.search(r"\bSilver\s+rate\s+is\s+" + _MONEY.pattern, summary, re.IGNORECASE)
    rates["Silver"] = silver_match.group(1) if silver_match else None
    return rates if all(rates.get(name) for name in ("24K", "22K", "18K", "Silver")) else None


def _table_rates(soup: BeautifulSoup) -> dict[str, str] | None:
    required = {"24K", "22K", "18K", "Silver"}
    for table in soup.find_all("table"):
        rates = {}
        for row in table.find_all("tr"):
            row_text = row.get_text(" ", strip=True)
            gold_label = re.match(r"Gold\s+(24K|22K|18K)\b", row_text, re.IGNORECASE)
            silver_label = re.match(r"Silver\b", row_text, re.IGNORECASE)
            label = gold_label.group(1).upper() if gold_label else "Silver" if silver_label else None
            amount = _MONEY.search(row_text)
            if label and amount:
                rates[label] = amount.group(1)
        if required.issubset(rates):
            return rates
    return None


def extract_rates(html: str) -> RateQuote:
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    rates = _summary_rates(text) or _table_rates(soup)
    if not rates:
        raise RateSourceError("Could not safely identify all four rates in Goldmeter's live summary or rates table")
    return RateQuote(
        gold_24k=rates["24K"],
        gold_22k=rates["22K"],
        gold_18k=rates["18K"],
        silver=rates["Silver"],
    )


def fetch_rates(url: str) -> RateQuote:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "goldmeter.in":
        raise RateSourceError("Rate URL must use HTTPS and the exact goldmeter.in host")

    try:
        response = requests.get(
            url,
            headers={"User-Agent": "GoldSilverRateNotifier/1.0"},
            timeout=20,
            allow_redirects=False,
        )
    except requests.RequestException as exc:
        raise RateSourceError(f"Unable to fetch Goldmeter: {exc}") from exc

    if 300 <= response.status_code < 400:
        raise RateSourceError("Goldmeter redirected the request; refusing to use redirected content")
    if not 200 <= response.status_code < 300:
        raise RateSourceError(f"Goldmeter returned HTTP {response.status_code}")
    if urlparse(response.url).hostname != "goldmeter.in":
        raise RateSourceError("Response came from an unexpected host")
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise RateSourceError("Goldmeter response was not HTML")

    return extract_rates(response.text)
