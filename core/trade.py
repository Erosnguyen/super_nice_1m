import asyncio
import aiohttp
import pandas as pd
import mplfinance as mpf
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ✅ Binance API URL
BINANCE_API_URL = "https://api.binance.com/api/v3/klines"

# ✅ Semaphore to Limit Concurrent Requests (Avoid Rate Limits)
SEMAPHORE = asyncio.Semaphore(5)  # Binance allows 1200 requests/minute

# 🔥 Function to Fetch OHLC Data Asynchronously
async def fetch_ohlc(session, symbol, interval, limit=100):
    url = f"{BINANCE_API_URL}?symbol={symbol}&interval={interval}&limit={limit}"
    async with SEMAPHORE:
        try:
            async with session.get(url) as response:
                data = await response.json()
                
                if "code" in data:  # Handle API errors
                    print(f"❌ Binance API Error: {data}")
                    return interval, None

                # Convert to DataFrame
                df = pd.DataFrame(data, columns=[
                    "timestamp", "open", "high", "low", "close", "volume",
                    "close_time", "quote_asset_volume", "num_trades",
                    "taker_buy_base", "taker_buy_quote", "ignore"
                ])
                
                # Convert timestamp to datetime
                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                
                # Convert price columns to float
                df["open"] = df["open"].astype(float)
                df["high"] = df["high"].astype(float)
                df["low"] = df["low"].astype(float)
                df["close"] = df["close"].astype(float)
                df["volume"] = df["volume"].astype(float)
                
                return interval, df[["timestamp", "open", "high", "low", "close", "volume"]]
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return interval, None

# ✅ Fetch Multiple Timeframes Asynchronously
async def fetch_all_timeframes(symbol="BTCUSDT", timeframes=["1m", "5m", "1h", "1d"], limit=100):
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_ohlc(session, symbol, interval, limit) for interval in timeframes]
        results = await asyncio.gather(*tasks)
        return {interval: df for interval, df in results if df is not None}  # Filter failed requests

# 📌 Strategy: Combined VWMA, Breakout, and Volume Surge
def calculate_vwma(df, window=14):
    """Calculate Volume-Weighted Moving Average (VWMA)."""
    df["VWMA"] = (df["close"] * df["volume"]).rolling(window=window).sum() / df["volume"].rolling(window=window).sum()
    return df
def calculate_rsi(df, window=14):
    """Calculate the Relative Strength Index (RSI)."""
    delta = df["close"].diff(1)
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    df["RSI"] = 100 - (100 / (1 + rs))
    return df
def calculate_macd(df, short_window=12, long_window=26, signal_window=9):
    """Calculate the Moving Average Convergence Divergence (MACD)."""
    df["MACD"] = df["close"].ewm(span=short_window, adjust=False).mean() - df["close"].ewm(span=long_window, adjust=False).mean()
    df["Signal"] = df["MACD"].ewm(span=signal_window, adjust=False).mean()
    df["MACD_Histogram"] = df["MACD"] - df["Signal"]
    return df
def calculate_bollinger_bands(df, window=20, num_std=2):
    """Calculate Bollinger Bands."""
    df["SMA"] = df["close"].rolling(window=window).mean()
    df["Upper_Band"] = df["SMA"] + (df["close"].rolling(window=window).std() * num_std)
    df["Lower_Band"] = df["SMA"] - (df["close"].rolling(window=window).std() * num_std)
    return df

def multi_strategy_trading(df):
    df = calculate_vwma(df)
    df = calculate_rsi(df)
    df = calculate_macd(df)
    df = calculate_bollinger_bands(df)

    df["High_Max"] = df["high"].rolling(20).max()
    df["Low_Min"] = df["low"].rolling(20).min()
    avg_volume = df["volume"].rolling(20).mean()

    buy_signals = []
    sell_signals = []
    position = None

    for i in range(20, len(df)):
        buy_count = 0
        sell_count = 0

        # ✅ VWMA Trend Confirmation
        if df["close"][i] > df["VWMA"][i] and df["volume"][i] > avg_volume[i]:
            buy_count += 1
        elif df["close"][i] < df["VWMA"][i] and df["volume"][i] > avg_volume[i]:
            sell_count += 1

        # ✅ Volume Breakout
        if df["close"][i] > df["High_Max"][i-1] and df["volume"][i] > avg_volume[i]:
            buy_count += 1
        elif df["close"][i] < df["Low_Min"][i-1] and df["volume"][i] > avg_volume[i]:
            sell_count += 1

        # ✅ Volume Surge Reversal
        if df["volume"][i] > 2 * avg_volume[i]:
            if df["close"][i] < df["close"][i-1]:  
                buy_count += 1
            elif df["close"][i] > df["close"][i-1]:  
                sell_count += 1

        # ✅ RSI Confirmation
        if df["RSI"][i] < 30:  # Oversold condition
            buy_count += 1
        elif df["RSI"][i] > 70:  # Overbought condition
            sell_count += 1

        # ✅ MACD Confirmation
        if df["MACD"][i] > df["Signal"][i]:  
            buy_count += 1
        elif df["MACD"][i] < df["Signal"][i]:  
            sell_count += 1

        # ✅ Bollinger Band Confirmation
        if df["close"][i] <= df["Lower_Band"][i]:  
            buy_count += 1
        elif df["close"][i] >= df["Upper_Band"][i]:  
            sell_count += 1

        # 📈 Buy Condition: At least 3 strategies confirm
        if buy_count >= 3:
            if position != "BUY":
                buy_signals.append(df["timestamp"][i])
                position = "BUY"

        # 📉 Sell Condition: At least 3 strategies confirm
        elif sell_count >= 3:
            if position != "SELL":
                sell_signals.append(df["timestamp"][i])
                position = "SELL"

    return buy_signals, sell_signals


# 🔴 Function to Plot Candlestick Chart with Volume & Signals
def plot_candlestick_with_signals(df, title, buy_signals, sell_signals):
    # Create a subplot with 2 rows (1 for price, 1 for volume)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        row_heights=[0.7, 0.3],  # Adjust heights
                        vertical_spacing=0.1,   # Space between plots
                        subplot_titles=(title, "Trading Volume"))

    # 📊 Add Candlestick Chart
    fig.add_trace(go.Candlestick(
        x=df["timestamp"],
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Candlesticks",
        increasing_line_color='green',
        decreasing_line_color='red'
    ), row=1, col=1)

    # 🔼 Buy Signals (Green Up Arrows)
    fig.add_trace(go.Scatter(
        x=buy_signals,
        y=[df.loc[df["timestamp"] == t, "low"].values[0] * 0.98 for t in buy_signals],  # Slightly below low price
        mode="markers",
        marker=dict(symbol="triangle-up", size=12, color="green"),
        name="Buy Signal"
    ), row=1, col=1)

    # 🔽 Sell Signals (Red Down Arrows)
    fig.add_trace(go.Scatter(
        x=sell_signals,
        y=[df.loc[df["timestamp"] == t, "high"].values[0] * 1.02 for t in sell_signals],  # Slightly above high price
        mode="markers",
        marker=dict(symbol="triangle-down", size=12, color="red"),
        name="Sell Signal"
    ), row=1, col=1)

    # 🔵 Add Volume Bar Chart
    colors = ['green' if df["close"][i] >= df["open"][i] else 'red' for i in range(len(df))]
    
    fig.add_trace(go.Bar(
        x=df["timestamp"],
        y=df["volume"],
        name="Volume",
        marker=dict(color=colors),
        opacity=0.8
    ), row=2, col=1)

    # 🎨 Layout Styling
    fig.update_layout(
        title=title,
        xaxis=dict(title="Time", rangeslider_visible=False),
        yaxis=dict(title="Price (USDT)", side="right"),
        yaxis2=dict(title="Volume", side="right"),
        height=800,
        template="plotly_dark"
    )

    fig.show()

# ✅ Run the Async Data Collection
timeframes = ["30m", "1h", "4h", "1d"]  # Multiple timeframes
df_dict = asyncio.run(fetch_all_timeframes(symbol="BTCUSDT", timeframes=timeframes, limit=50))

# 🔥 Apply Multi-Strategy Trading System and Plot
for interval, df in df_dict.items():
    print(f"📊 Processing {interval} timeframe")

    # Apply trading strategy
    buy_signals, sell_signals = multi_strategy_trading(df)

    # Plot chart with signals
    plot_candlestick_with_signals(df, f"BTC/USDT {interval} Candlestick & Volume Chart", buy_signals, sell_signals)

    print(f"🚀 {interval} - BUY signals:", buy_signals)
    print(f"📉 {interval} - SELL signals:", sell_signals)
