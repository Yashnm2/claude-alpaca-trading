import re
import requests
from bs4 import BeautifulSoup
from dataclasses import dataclass
from datetime import datetime

POLITICIAN_ID = "P000197"
POLITICIAN_NAME = "Nancy Pelosi"
POLITICIAN_URL = f"https://www.capitoltrades.com/politicians/{POLITICIAN_ID}"

# Dollar midpoints for each reported size bucket
SIZE_MIDPOINTS: dict[str, int] = {
    "1K–15K":     8_000,
    "15K–50K":    32_500,
    "50K–100K":   75_000,
    "100K–250K":  175_000,
    "250K–500K":  375_000,
    "500K–1M":    750_000,
    "1M–5M":    3_000_000,
    "5M–25M":  15_000_000,
    "25M+":    30_000_000,
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}


@dataclass
class Trade:
    trade_id: str
    politician: str
    issuer: str
    ticker: str           # e.g. "NVDA"
    traded_date: str      # YYYY-MM-DD
    published_date: str   # YYYY-MM-DD
    action: str           # "buy" or "sell"
    size_label: str       # e.g. "1M–5M"
    size_midpoint: int    # dollar midpoint of size bucket


def _parse_date(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return text  # return raw if unparseable


def fetch_trades(url: str = POLITICIAN_URL) -> list[Trade]:
    """Fetch and parse the most recent trades for the configured politician."""
    resp = requests.get(url, headers=_HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "lxml")

    trades: list[Trade] = []
    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue

        link = row.find("a", href=re.compile(r"/trades/\d+"))
        if not link:
            continue
        trade_id = re.search(r"/trades/(\d+)", link["href"]).group(1)

        # Cell 0: "Issuer Name\nTICKER:EXCHANGE"
        cell0_lines = [l.strip() for l in cells[0].get_text(separator="\n").split("\n") if l.strip()]
        issuer = cell0_lines[0] if cell0_lines else ""
        ticker_raw = cell0_lines[1] if len(cell0_lines) > 1 else ""
        m = re.match(r"([A-Z][A-Z0-9.\-]+):([A-Z]+)", ticker_raw)
        if not m:
            continue  # skip bonds, munis, and unlisted securities
        ticker, exchange = m.group(1), m.group(2)
        if exchange != "US":
            continue  # Alpaca supports US-listed securities only

        # Cell 1: published date ("26 Jan 2026")
        published = _parse_date(cells[1].get_text(separator=" "))
        # Cell 2: traded date
        traded = _parse_date(cells[2].get_text(separator=" "))
        # Cell 4: BUY or SELL
        action = cells[4].get_text().strip().lower()
        if action not in ("buy", "sell"):
            continue
        # Cell 5: size label
        size_label = cells[5].get_text().strip()

        trades.append(Trade(
            trade_id=trade_id,
            politician=POLITICIAN_NAME,
            issuer=issuer,
            ticker=ticker,
            traded_date=traded,
            published_date=published,
            action=action,
            size_label=size_label,
            size_midpoint=SIZE_MIDPOINTS.get(size_label, 8_000),
        ))

    return trades


if __name__ == "__main__":
    print(f"Fetching trades for {POLITICIAN_NAME}…")
    for t in fetch_trades():
        print(f"  [{t.trade_id}] {t.action.upper():4s} {t.ticker:6s} {t.size_label:12s} traded={t.traded_date}  published={t.published_date}")
