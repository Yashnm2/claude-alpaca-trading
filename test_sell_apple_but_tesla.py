import requests

headers = {
    "APCA-API-KEY-ID": "PKRBBLOSMGJWYYQPMJL3KVC6VZ",
    "APCA-API-SECRET-KEY": "9KtxQ1vuC9AWrCJfbfHcLir1DV7z57p5u7gajvrcvRDX",
}
BASE = "https://paper-api.alpaca.markets/v2"

# Sell 1 share of AAPL
sell = requests.post(f"{BASE}/orders", headers=headers, json={
    "symbol": "AAPL",
    "qty": "1",
    "side": "sell",
    "type": "market",
    "time_in_force": "day",
})
print("SELL AAPL:", sell.status_code, sell.json())

# Buy 1 share of TSLA
buy = requests.post(f"{BASE}/orders", headers=headers, json={
    "symbol": "TSLA",
    "qty": "1",
    "side": "buy",
    "type": "market",
    "time_in_force": "day",
})
print("BUY TSLA:", buy.status_code, buy.json())