import asyncio
import aiohttp
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ✅ Binance API URL
BINANCE_API_URL = "https://api.binance.com/api/v3/klines"
SEMAPHORE = asyncio.Semaphore(5)

# 🔥 Fetch OHLC Data Asynchronously
async def fetch_ohlc(session, symbol, interval, limit=200):
    url = f"{BINANCE_API_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    async with SEMAPHORE:
        try:
            async with session.get(url) as response:
                data = await response.json()
                if "code" in data:
                    print(f"❌ Binance API Error: {data}")
                    return interval, None

                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "num_trades",
                    "taker_buy_base", "taker_buy_quote", "ignore"
                ])
                
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                df[["open", "high", "low", "close", "volume"]] = df[["open", "high", "low", "close", "volume"]].astype(float)
                
                return interval, df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return interval, None

async def fetch_all_timeframes(symbol="BTCUSDT", timeframes=["15m", "30m", "1h"], limit=200):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_ohlc(session, symbol, interval, limit) for interval in timeframes]
        results = await asyncio.gather(*tasks)
        return {interval: df for interval, df in results if df is not None}

# 📌 Essential Indicators (Less Restrictive)
def calculate_rsi(df, window=14):
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

# 📊 Simplified Trading Strategy
def multi_strategy_trading(df):
    df = calculate_rsi(df)
    df = calculate_market_structure(df)
    df = calculate_smart_money_divergence(df)

    buy_signals = []
    sell_signals = []
    position = None

    for i in range(14, len(df)):  # Start after 14 bars to match RSI
        buy_count = 0
        sell_count = 0

        # ✅ RSI Confirmation (Reduced Restriction)
        if df["RSI"][i] < 40: buy_count += 1  # Changed from 30 to 40 to allow more trades
        if df["RSI"][i] > 60: sell_count += 1  # Changed from 70 to 60 to allow more trades

        # ✅ Market Structure Shift (MSS) Confirmation
        if df["MSS_Bullish"][i]: buy_count += 1
        if df["MSS_Bearish"][i]: sell_count += 1

        # ✅ Smart Money Divergence (SMD) Confirmation
        if df["Bullish_Divergence"][i]: buy_count += 1
        if df["Bearish_Divergence"][i]: sell_count += 1

        # 📈 Buy/Sell Conditions
        if buy_count >= 2 and position != "BUY":  # Reduced threshold from 3 to 2
            buy_signals.append(df["timestamp"][i])
            position = "BUY"
        elif sell_count >= 2 and position != "SELL":
            sell_signals.append(df["timestamp"][i])
            position = "SELL"

    return buy_signals, sell_signals

# 📈 Plot with Buy/Sell Signals
def plot_candlestick_with_signals(df, title, buy_signals, sell_signals):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.1)

    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Candlesticks"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=buy_signals,
        y=[df.loc[df["timestamp"] == t, "low"].values[0] * 0.98 for t in buy_signals],
        mode="markers",
        marker=dict(symbol="triangle-up", size=12, color="green"),
        name="Buy Signal"
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=sell_signals,
        y=[df.loc[df["timestamp"] == t, "high"].values[0] * 1.02 for t in sell_signals],
        mode="markers",
        marker=dict(symbol="triangle-down", size=12, color="red"),
        name="Sell Signal"
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df["timestamp"], y=df["volume"], name="Volume"), row=2, col=1)
    fig.update_layout(title=title, template="plotly_dark", height=800)
    fig.show()

# ✅ Run
df_dict = asyncio.run(fetch_all_timeframes(symbol="BTCUSDT", timeframes=["15m", "30m", "1h"], limit=200))
for interval, df in df_dict.items():
    buy_signals, sell_signals = multi_strategy_trading(df)
    plot_candlestick_with_signals(df, f"BTC/USDT {interval} Candlestick & Volume", buy_signals, sell_signals)
