"""
Capitol Trades Copy Bot
-----------------------
Polls Nancy Pelosi's Capitol Trades page for newly disclosed stock trades
and mirrors them on Alpaca (paper or live, depending on ALPACA_BASE_URL).

Run directly:   python bot.py
Scheduled via:  cron / Claude Code scheduler (see README)
"""

import io
import json
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows so log symbols print correctly
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

from scraper import fetch_trades, POLITICIAN_NAME, POLITICIAN_URL
from executor import execute_trade, get_account

_STATE_FILE = Path(__file__).parent / "state.json"
_LOG_FILE   = Path(__file__).parent / "trades.log"


# ── State helpers ─────────────────────────────────────────────────────────────

def _load_state() -> dict:
    if _STATE_FILE.exists():
        return json.loads(_STATE_FILE.read_text())
    return {"seen_trade_ids": [], "last_check": None, "executions": []}


def _save_state(state: dict) -> None:
    _STATE_FILE.write_text(json.dumps(state, indent=2, default=str))


# ── Logging ───────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(_LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


# ── Main ──────────────────────────────────────────────────────────────────────

def run() -> None:
    _log("=" * 60)
    _log(f"Capitol Trades Bot — mirroring {POLITICIAN_NAME}")
    _log("=" * 60)

    # Verify Alpaca connectivity
    try:
        acct = get_account()
        _log(f"Alpaca account: {acct.get('account_number')}  "
             f"buying_power=${float(acct.get('buying_power', 0)):,.2f}  "
             f"status={acct.get('status')}")
    except Exception as e:
        _log(f"[ERROR] Cannot reach Alpaca API: {e}")
        sys.exit(1)

    state = _load_state()
    seen: set[str] = set(state.get("seen_trade_ids", []))

    _log(f"Fetching trades from Capitol Trades …")
    try:
        all_trades = fetch_trades()
    except Exception as e:
        _log(f"[ERROR] Scraper failed: {e}")
        sys.exit(1)

    _log(f"  Found {len(all_trades)} US-listed trade(s) on page")

    new_trades = [t for t in all_trades if t.trade_id not in seen]
    _log(f"  {len(new_trades)} new trade(s) to action")

    for trade in new_trades:
        _log(
            f"\n  >> [{trade.trade_id}] {trade.action.upper()} "
            f"{trade.ticker} ({trade.size_label})  "
            f"traded={trade.traded_date}  disclosed={trade.published_date}"
        )

        try:
            order = execute_trade(trade)
        except Exception as e:
            _log(f"     [ERROR] {e}")
            seen.add(trade.trade_id)  # mark seen to avoid retry loop
            continue

        if order:
            _log(
                f"     OK Alpaca order {order.get('id')}  "
                f"side={order.get('side')}  qty={order.get('qty')}  "
                f"status={order.get('status')}"
            )
            state.setdefault("executions", []).append({
                "trade_id": trade.trade_id,
                "ticker": trade.ticker,
                "action": trade.action,
                "alpaca_order_id": order.get("id"),
                "executed_at": datetime.now().isoformat(),
            })
        else:
            _log(f"     -- Skipped (no position to sell / insufficient funds / qty too small)")

        seen.add(trade.trade_id)

    state["seen_trade_ids"] = sorted(seen)
    state["last_check"] = datetime.now().isoformat()
    _save_state(state)

    _log(f"\nDone. Tracking {len(seen)} trade ID(s) total.")


if __name__ == "__main__":
    run()
