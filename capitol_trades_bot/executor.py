import os
import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

_KEY    = os.getenv("ALPACA_API_KEY")
_SECRET = os.getenv("ALPACA_SECRET_KEY")
_BASE   = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
_DATA   = "https://data.alpaca.markets/v2"

# How many dollars to deploy per trade (overridden by env var)
TRADE_USD = float(os.getenv("TRADE_USD_AMOUNT", "500"))

_HEADERS = {
    "APCA-API-KEY-ID": _KEY,
    "APCA-API-SECRET-KEY": _SECRET,
}


def get_account() -> dict:
    r = requests.get(f"{_BASE}/account", headers=_HEADERS, timeout=15)
    r.raise_for_status()
    return r.json()


def get_latest_price(ticker: str) -> float:
    r = requests.get(
        f"{_DATA}/stocks/{ticker}/trades/latest",
        headers=_HEADERS,
        params={"feed": "iex"},
        timeout=15,
    )
    r.raise_for_status()
    return float(r.json()["trade"]["p"])


def get_position(ticker: str) -> dict | None:
    r = requests.get(f"{_BASE}/positions/{ticker}", headers=_HEADERS, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def place_order(ticker: str, qty: float, side: str) -> dict:
    r = requests.post(
        f"{_BASE}/orders",
        headers=_HEADERS,
        json={
            "symbol": ticker,
            "qty": str(qty),
            "side": side,
            "type": "market",
            "time_in_force": "day",
        },
        timeout=15,
    )
    r.raise_for_status()
    return r.json()


def execute_trade(trade) -> dict | None:
    """
    Mirror a politician's trade on Alpaca.

    Buy: spend TRADE_USD dollars in fractional shares.
    Sell: liquidate whatever position we hold.

    Returns the Alpaca order dict, or None if the trade was skipped.
    """
    ticker = trade.ticker
    action = trade.action  # "buy" or "sell"

    if action == "sell":
        pos = get_position(ticker)
        if not pos or float(pos.get("qty", 0)) <= 0:
            return None  # nothing to sell
        qty = round(float(pos["qty"]), 6)
        return place_order(ticker, qty, "sell")

    # action == "buy"
    acct = get_account()
    buying_power = float(acct.get("buying_power", 0))
    if buying_power < TRADE_USD:
        return None  # insufficient funds

    price = get_latest_price(ticker)
    qty = round(TRADE_USD / price, 6)
    if qty < 0.001:
        return None  # price too high for configured trade size

    return place_order(ticker, qty, "buy")
