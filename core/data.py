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

# 🔵 Function to Plot Static Candlestick Chart (mplfinance)
def plot_candlestick_static(df, title):
    df = df.set_index("timestamp")
    fig, ax = mpf.plot(df, type="candle", style="charles",
                        title=title, ylabel="Price (USDT)", volume=True,
                        returnfig=True)
    plt.show()

# 🔴 Function to Plot Candlestick Chart with Volume (Plotly) - Fixed Scaling
def plot_candlestick_with_volume(df, title):
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

    # 🔵 Add Volume Bar Chart (Color based on price movement)
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
        yaxis=dict(title="Price (USDT)", side="right"),  # Main price axis
        yaxis2=dict(title="Volume", side="right"),  # Volume axis
        height=800,  # Increased height for better readability
        template="plotly_dark"
    )

    fig.show()

# ✅ Run the Async Data Collection
timeframes = ["1m", "5m", "1h", "1d"]  # Multiple timeframes
df_dict = asyncio.run(fetch_all_timeframes(symbol="BTCUSDT", timeframes=timeframes, limit=50))

# 🔥 Plot for Each Timeframe
for interval, df in df_dict.items():
    print(f"📊 Plotting {interval} timeframe")
    plot_candlestick_static(df, f"BTC/USDT {interval} Candlestick Chart")
    plot_candlestick_with_volume(df, f"BTC/USDT {interval} Candlestick & Volume Chart")
