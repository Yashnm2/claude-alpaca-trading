import requests

url = "https://paper-api.alpaca.markets/v2/orders"
headers = {
    "APCA-API-KEY-ID": "PKRBBLOSMGJWYYQPMJL3KVC6VZ",
    "APCA-API-SECRET-KEY": "9KtxQ1vuC9AWrCJfbfHcLir1DV7z57p5u7gajvrcvRDX",
}
payload = {
    "symbol": "AAPL",
    "qty": "1",
    "side": "buy",
    "type": "market",
    "time_in_force": "day",
}

response = requests.post(url, json=payload, headers=headers)
print(response.status_code, response.json())