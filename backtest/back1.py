import requests
import pandas as pd
import numpy as np
import ta
import matplotlib.pyplot as plt

# Binance API URL
BINANCE_API_URL = "https://api.binance.com/api/v3/klines"

# Trade Settings
PAIR = "BTCUSDT"
INTERVAL = "5m"  # 5-minute timeframe
LIMIT = 2000  # Fetch more historical data

# Fetch BTC Data from Binance
def get_binance_data(symbol, interval, limit):
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    response = requests.get(BINANCE_API_URL, params=params)
    data = response.json()
    
    df = pd.DataFrame(data, columns=[
        "timestamp", "open", "high", "low", "close", "volume", "close_time",
        "quote_asset_volume", "trades", "taker_buy_base", "taker_buy_quote", "ignore"
    ])
    
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["close"] = df["close"].astype(float)
    return df

# Compute Technical Indicators
def apply_indicators(df):
    df["9EMA"] = ta.trend.ema_indicator(df["close"], window=9)
    df["21EMA"] = ta.trend.ema_indicator(df["close"], window=21)
    df["RSI"] = ta.momentum.rsi(df["close"], window=14)
    
    macd = ta.trend.macd(df["close"])
    macd_signal = ta.trend.macd_signal(df["close"])
    df["MACD"] = macd
    df["MACD_Signal"] = macd_signal

    return df

# Backtest Trading Strategy
def backtest(df, initial_balance=10000, risk_per_trade=2):
    balance = initial_balance
    position = None  # 'long' or 'short'
    trade_history = []

    for i in range(1, len(df)):
        # More flexible entry conditions
        if df["9EMA"].iloc[i] > df["21EMA"].iloc[i] and df["RSI"].iloc[i] > 45 and df["MACD"].iloc[i] > df["MACD_Signal"].iloc[i]:
            signal = "BUY"
        elif df["9EMA"].iloc[i] < df["21EMA"].iloc[i] and df["RSI"].iloc[i] < 55 and df["MACD"].iloc[i] < df["MACD_Signal"].iloc[i]:
            signal = "SELL"
        else:
            signal = None

        # Execute trade
        if signal == "BUY" and position is None:
            entry_price = df["close"].iloc[i]
            stop_loss = entry_price * (1 - risk_per_trade / 100)
            position = "long"
            trade_history.append({"Type": "BUY", "Entry Price": entry_price, "Stop Loss": stop_loss, "Exit Price": None, "Profit": 0})

        elif signal == "SELL" and position is None:
            entry_price = df["close"].iloc[i]
            stop_loss = entry_price * (1 + risk_per_trade / 100)
            position = "short"
            trade_history.append({"Type": "SELL", "Entry Price": entry_price, "Stop Loss": stop_loss, "Exit Price": None, "Profit": 0})

        # Exit Trade
        if position == "long" and df["close"].iloc[i] < stop_loss:
            trade_history[-1]["Exit Price"] = df["close"].iloc[i]
            trade_history[-1]["Profit"] = df["close"].iloc[i] - trade_history[-1]["Entry Price"]
            balance += trade_history[-1]["Profit"]
            position = None

        elif position == "short" and df["close"].iloc[i] > stop_loss:
            trade_history[-1]["Exit Price"] = df["close"].iloc[i]
            trade_history[-1]["Profit"] = trade_history[-1]["Entry Price"] - df["close"].iloc[i]
            balance += trade_history[-1]["Profit"]
            position = None

    return trade_history, balance

# 📊 Run Backtest and Save Results
df = get_binance_data(PAIR, INTERVAL, LIMIT)
df = apply_indicators(df)
trade_history, final_balance = backtest(df)

# Save results to CSV
df_trades = pd.DataFrame(trade_history)

# Debugging: Check column names
print("\nTrade History Columns:", df_trades.columns)

# Fix: Ensure 'Profit' column exists
if 'Profit' in df_trades.columns and len(df_trades) > 0:
    win_rate = len(df_trades[df_trades['Profit'] > 0]) / len(df_trades) * 100
    max_drawdown = df_trades["Profit"].min()
else:
    win_rate = 0
    max_drawdown = 0

# Print Summary
print(f"\n📊 Backtest Results:\n")
print(f"🔹 Initial Balance: $10,000")
print(f"🔹 Final Balance: ${final_balance:.2f}")
print(f"🔹 Total Trades: {len(df_trades)}")
print(f"🔹 Win Rate: {win_rate:.2f}%")
print(f"🔹 Max Drawdown: {max_drawdown}")

# 📈 Plot Profit/Loss Over Time and Save as Image
if "Profit" in df_trades.columns and len(df_trades) > 0:
    plt.figure(figsize=(10,5))
    plt.plot(df_trades.index, df_trades["Profit"].cumsum(), label="Cumulative Profit")
    plt.axhline(y=0, color="r", linestyle="--", label="Break-even")
    plt.xlabel("Trade Number")
    plt.ylabel("Profit ($)")
    plt.title("BTC Trading Strategy Performance")
    plt.legend()
    
    # Save the plot as an image
    plt.savefig("backtest_result.png")
    print("\n📊 Backtest Graph saved as 'backtest_result.png'")

    # Uncomment to show the plot (may not work in non-GUI environments)
    # plt.show()
