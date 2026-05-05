import requests
import os
import sys
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

HEADERS = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
}
BASE = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets/v2")
DATA = "https://data.alpaca.markets/v2"
SYMBOL = "TSLA"

STOP_LOSS_PCT  = 0.10
TRAIL_TRIGGER  = 0.10
TRAIL_FLOOR    = 0.05
INITIAL_QTY    = 10
LADDER_20_DROP = 0.20
LADDER_20_QTY  = 20
LADDER_30_DROP = 0.30
LADDER_30_QTY  = 10


def log(msg):
    print(f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}] {msg}", flush=True)


def get_position():
    r = requests.get(f"{BASE}/positions/{SYMBOL}", headers=HEADERS)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.json()


def get_latest_price():
    r = requests.get(
        f"{DATA}/stocks/{SYMBOL}/trades/latest",
        headers=HEADERS,
        params={"feed": "iex"},
    )
    r.raise_for_status()
    return float(r.json()["trade"]["p"])


def get_max_recent_price(days=60):
    start = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(
        f"{DATA}/stocks/{SYMBOL}/bars",
        headers=HEADERS,
        params={"timeframe": "1Day", "start": start, "feed": "iex", "limit": 100},
    )
    r.raise_for_status()
    bars = r.json().get("bars", [])
    return max((b["h"] for b in bars), default=None) if bars else None


def place_order(qty, side):
    r = requests.post(
        f"{BASE}/orders",
        headers=HEADERS,
        json={"symbol": SYMBOL, "qty": str(qty), "side": side, "type": "market", "time_in_force": "day"},
    )
    r.raise_for_status()
    return r.json()


def main():
    log("=== TSLA Strategy Monitor ===")

    pos = get_position()
    if not pos:
        log("No TSLA position found. Nothing to do.")
        sys.exit(0)

    qty   = int(float(pos["qty"]))
    entry = float(pos["avg_entry_price"])
    price = get_latest_price()
    pct   = (price - entry) / entry * 100

    log(f"Position : {qty} shares")
    log(f"Entry    : ${entry:.2f}")
    log(f"Current  : ${price:.2f} ({pct:+.2f}%)")

    max_price = get_max_recent_price(60) or price
    log(f"60d high : ${max_price:.2f}")

    base_stop = entry * (1 - STOP_LOSS_PCT)
    if max_price >= entry * (1 + TRAIL_TRIGGER):
        trailing_stop = max(base_stop, max_price * (1 - TRAIL_FLOOR))
        log(f"Stop     : ${trailing_stop:.2f} (trailing — 5% below 60d high)")
    else:
        trailing_stop = base_stop
        log(f"Stop     : ${trailing_stop:.2f} (fixed -10% from entry, trail not yet active)")

    ladder_20_done = qty >= INITIAL_QTY + LADDER_20_QTY
    ladder_30_done = qty >= INITIAL_QTY + LADDER_20_QTY + LADDER_30_QTY
    log(f"Ladder -20% done: {ladder_20_done} | Ladder -30% done: {ladder_30_done}")

    if price <= trailing_stop:
        log(f">>> STOP LOSS triggered at ${price:.2f} (stop: ${trailing_stop:.2f})")
        o = place_order(qty, "sell")
        log(f">>> SELL {qty} shares — ID: {o['id']} | Status: {o['status']}")
    else:
        actions = []

        if not ladder_20_done and price <= entry * (1 - LADDER_20_DROP):
            log(f">>> LADDER -20% triggered at ${price:.2f}")
            o = place_order(LADDER_20_QTY, "buy")
            log(f">>> BUY {LADDER_20_QTY} shares — ID: {o['id']} | Status: {o['status']}")
            actions.append("ladder_20")

        if not ladder_30_done and price <= entry * (1 - LADDER_30_DROP):
            log(f">>> LADDER -30% triggered at ${price:.2f}")
            o = place_order(LADDER_30_QTY, "buy")
            log(f">>> BUY {LADDER_30_QTY} shares — ID: {o['id']} | Status: {o['status']}")
            actions.append("ladder_30")

        if not actions:
            log("No action needed. All levels within range.")

    log("=== Done ===")


if __name__ == "__main__":
    main()
