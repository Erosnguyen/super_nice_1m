from flask import Flask, jsonify
import asyncio
import aiohttp
import pandas as pd

app = Flask(__name__)

BINANCE_API_URL = "https://api.binance.com/api/v3/klines"

async def fetch_ohlc(symbol="BTCUSDT", interval="15m", limit=50):
    """Fetch real-time market data from Binance"""
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
            
            return df

def calculate_rsi(df, window=14):
    """Calculate RSI Indicator"""
    delta = df["close"].diff(1)
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df

def calculate_market_structure(df):
    """Detect Market Structure Shift (MSS)"""
    df["MSS_Bullish"] = (df["high"] > df["high"].shift(1)) & (df["low"] > df["low"].shift(1))
    df["MSS_Bearish"] = (df["high"] < df["high"].shift(1)) & (df["low"] < df["low"].shift(1))
    return df

def calculate_smart_money_divergence(df):
    """Detect Smart Money Divergence (SMD) using RSI"""
    df["OBV"] = (df["volume"] * ((df["close"] > df["close"].shift(1)) * 2 - 1)).cumsum()
    df["Bearish_Divergence"] = (df["high"] > df["high"].shift(1)) & (df["RSI"] < df["RSI"].shift(1))
    df["Bullish_Divergence"] = (df["low"] < df["low"].shift(1)) & (df["RSI"] > df["RSI"].shift(1))
    return df

def multi_strategy_trading(df):
    """Run Strategy and Generate Buy/Sell Signals"""
    df = calculate_rsi(df)
    df = calculate_market_structure(df)
    df = calculate_smart_money_divergence(df)

    df["Buy_Signal"] = (df["RSI"] < 40) | df["MSS_Bullish"] | df["Bullish_Divergence"]
    df["Sell_Signal"] = (df["RSI"] > 60) | df["MSS_Bearish"] | df["Bearish_Divergence"]

    return df.to_dict(orient="records")

@app.route('/strategy', methods=['GET'])
def strategy():
    """Fetch Live Data, Process Signals, and Return Results"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    df = loop.run_until_complete(fetch_ohlc())

    if df is None:
        return jsonify({"error": "Failed to fetch data"}), 500

    processed_data = multi_strategy_trading(df)
    return jsonify(processed_data)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)
