import requests
import os
import time
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

HEADERS = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_API_KEY"),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET_KEY"),
}
BASE = os.getenv("ALPACA_BASE_URL")
DATA_BASE = "https://data.alpaca.markets/v2"
SYMBOL = "TSLA"

# ── Strategy parameters ──────────────────────────────────────────────────────
INITIAL_QTY       = 10      # shares to buy at open
STOP_LOSS_PCT     = 0.10    # sell everything if price drops 10% from entry
TRAIL_TRIGGER_PCT = 0.10    # start trailing after +10% gain
TRAIL_FLOOR_PCT   = 0.05    # trailing stop sits 5% below current price
LADDER_20_DROP    = 0.20    # buy more if price drops 20%
LADDER_20_QTY     = 20      # shares to add at -20%
LADDER_30_DROP    = 0.30    # buy more if price drops 30%
LADDER_30_QTY     = 10      # shares to add at -30%
POLL_INTERVAL     = 60      # seconds between price checks
# ─────────────────────────────────────────────────────────────────────────────

# NOTE: Stop loss triggers at -10%, ladder-in levels are at -20% and -30%.
# In a continuous market the stop loss will fire before the ladder levels are
# reached. Price gaps (e.g. overnight) could bypass the stop and hit a ladder
# level directly. Consider widening the stop or disabling it while laddering.


def place_order(symbol: str, qty: int, side: str) -> dict:
    resp = requests.post(
        f"{BASE}/orders",
        headers=HEADERS,
        json={
            "symbol": symbol,
            "qty": str(qty),
            "side": side,
            "type": "market",
            "time_in_force": "day",
        },
    )
    resp.raise_for_status()
    return resp.json()


def get_latest_price(symbol: str) -> float:
    resp = requests.get(
        f"{DATA_BASE}/stocks/{symbol}/trades/latest",
        headers=HEADERS,
        params={"feed": "iex"},
    )
    resp.raise_for_status()
    return float(resp.json()["trade"]["p"])


def print_order_summary(order: dict, label: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{'─' * 56}")
    print(f"  {label}")
    print(f"{'─' * 56}")
    print(f"  Time     : {ts}")
    print(f"  Order ID : {order.get('id', 'n/a')}")
    print(f"  Symbol   : {order.get('symbol')}")
    print(f"  Side     : {order.get('side', '').upper()}")
    print(f"  Qty      : {order.get('qty')}")
    print(f"  Type     : {order.get('type')}")
    print(f"  Status   : {order.get('status')}")
    print(f"{'─' * 56}\n")


def print_strategy_summary(entry: float, stop: float) -> None:
    print("\n╔══════════════════════════════════════════════════════╗")
    print("║              STRATEGY CONFIGURATION                 ║")
    print("╠══════════════════════════════════════════════════════╣")
    print(f"║  Symbol          : {SYMBOL:<34}║")
    print(f"║  Initial position: {INITIAL_QTY} shares                          ║")
    print(f"║  Entry price     : ${entry:<33.2f}║")
    print(f"║  Stop loss       : ${stop:<33.2f}║  (-{STOP_LOSS_PCT*100:.0f}%)")
    print(f"║  Trail activates : ${entry * (1 + TRAIL_TRIGGER_PCT):<33.2f}║  (+{TRAIL_TRIGGER_PCT*100:.0f}%)")
    print(f"║  Trail floor     : 5% below current price when trailing    ║")
    print(f"║  Ladder -20%     : buy {LADDER_20_QTY} shares @ ${entry * (1-LADDER_20_DROP):<18.2f}║")
    print(f"║  Ladder -30%     : buy {LADDER_30_QTY} shares @ ${entry * (1-LADDER_30_DROP):<18.2f}║")
    print("╠══════════════════════════════════════════════════════╣")
    print("║  ⚠  Stop loss (-10%) fires before ladder levels      ║")
    print("║     (-20%/-30%) in a continuous market. See NOTE     ║")
    print("║     at top of file if you want to adjust this.       ║")
    print("╚══════════════════════════════════════════════════════╝\n")


def run_strategy() -> None:
    # ── Step 1: initial market buy ───────────────────────────────────────────
    print(f"[{datetime.now()}] Placing initial buy: {INITIAL_QTY} shares of {SYMBOL} …")
    order = place_order(SYMBOL, INITIAL_QTY, "buy")
    print_order_summary(order, f"INITIAL BUY — {INITIAL_QTY} shares {SYMBOL}")

    # Give the order a moment to fill before sampling price
    time.sleep(3)
    entry_price: float = get_latest_price(SYMBOL)
    trailing_stop: float = entry_price * (1 - STOP_LOSS_PCT)
    position_qty: int = INITIAL_QTY
    ladder_20_done = False
    ladder_30_done = False

    print_strategy_summary(entry_price, trailing_stop)

    # ── Step 2: monitoring loop ──────────────────────────────────────────────
    while True:
        time.sleep(POLL_INTERVAL)

        try:
            price = get_latest_price(SYMBOL)
            pct   = (price - entry_price) / entry_price * 100
            print(
                f"[{datetime.now().strftime('%H:%M:%S')}]  "
                f"{SYMBOL}: ${price:.2f}  ({pct:+.2f}%)  |  "
                f"Stop: ${trailing_stop:.2f}  |  Held: {position_qty} shares"
            )

            # ── Trailing stop: raise floor when price climbs ─────────────────
            if price >= entry_price * (1 + TRAIL_TRIGGER_PCT):
                candidate = price * (1 - TRAIL_FLOOR_PCT)
                if candidate > trailing_stop:
                    trailing_stop = candidate
                    print(
                        f"  ↑ Trailing stop raised → ${trailing_stop:.2f}  "
                        f"(5% below ${price:.2f})"
                    )

            # ── Stop loss: sell everything ───────────────────────────────────
            if price <= trailing_stop:
                print(f"\n  ⚠  STOP LOSS triggered at ${price:.2f}")
                order = place_order(SYMBOL, position_qty, "sell")
                print_order_summary(
                    order, f"STOP LOSS SELL — {position_qty} shares {SYMBOL}"
                )
                print("Strategy complete. Position closed.")
                break

            # ── Ladder -20%: buy 20 shares ───────────────────────────────────
            if not ladder_20_done and price <= entry_price * (1 - LADDER_20_DROP):
                print(f"\n  📉  -20% level hit at ${price:.2f} — buying {LADDER_20_QTY} shares")
                order = place_order(SYMBOL, LADDER_20_QTY, "buy")
                print_order_summary(
                    order, f"LADDER BUY — {LADDER_20_QTY} shares {SYMBOL} @ -20%"
                )
                position_qty += LADDER_20_QTY
                ladder_20_done = True

            # ── Ladder -30%: buy 10 shares ───────────────────────────────────
            if not ladder_30_done and price <= entry_price * (1 - LADDER_30_DROP):
                print(f"\n  📉  -30% level hit at ${price:.2f} — buying {LADDER_30_QTY} shares")
                order = place_order(SYMBOL, LADDER_30_QTY, "buy")
                print_order_summary(
                    order, f"LADDER BUY — {LADDER_30_QTY} shares {SYMBOL} @ -30%"
                )
                position_qty += LADDER_30_QTY
                ladder_30_done = True

        except KeyboardInterrupt:
            print("\nStrategy manually stopped. Check your open positions on Alpaca.")
            break
        except Exception as e:
            print(f"  [ERROR] {e} — retrying next interval …")


if __name__ == "__main__":
    run_strategy()
