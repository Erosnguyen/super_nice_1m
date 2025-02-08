from flask import Flask, jsonify, request
import asyncio
import aiohttp
import pandas as pd

app = Flask(__name__)
BINANCE_API_URL = "https://api.binance.com/api/v3/klines"

async def fetch_ohlc(symbol, interval, limit=200):
    url = f"{BINANCE_API_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            if "code" in data:
                return None

            df = pd.DataFrame(data, columns=[
                "timestamp", "open", "high", "low", "close", "volume",
                "close_time", "quote_asset_volume", "num_trades",
                "taker_buy_base", "taker_buy_quote", "ignore"
            ])
            
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
            df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
            
            return df.to_dict(orient="records")

@app.route('/fetch_data', methods=['GET'])
def get_data():
    symbol = request.args.get("symbol", "BTCUSDT")
    interval = request.args.get("interval", "15m")
    limit = int(request.args.get("limit", 200))

    data = asyncio.run(fetch_ohlc(symbol, interval, limit))
    return jsonify(data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001)
