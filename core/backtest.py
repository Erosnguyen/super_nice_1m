import asyncio
import pandas as pd
import numpy as np
import aiohttp
from data import fetch_all_timeframes
from trade import multi_strategy_trading

# 📌 Backtesting Function
def backtest_strategy(df, strategy_name="Baseline", risk_reward_ratio=2.0):
    initial_balance = 10000
    balance = initial_balance
    trade_results = []
    open_trade = None  # Track active trade

    for i in range(len(df)):
        if open_trade is None:
            if df["Buy_Signal"][i]:
                open_trade = {
                    "entry_price": df["close"][i],
                    "stop_loss": df["close"][i] * 0.98,  # 2% stop-loss below entry price
                    "take_profit": df["close"][i] * (1 + 0.02 * risk_reward_ratio),  # 2x SL
                    "trade_type": "BUY"
                }
            elif df["Sell_Signal"][i]:
                open_trade = {
                    "entry_price": df["close"][i],
                    "stop_loss": df["close"][i] * 1.02,  # 2% stop-loss above entry price
                    "take_profit": df["close"][i] * (1 - 0.02 * risk_reward_ratio),  # 2x SL
                    "trade_type": "SELL"
                }
        else:
            if open_trade["trade_type"] == "BUY":
                if df["high"][i] >= open_trade["take_profit"]:
                    profit = (open_trade["take_profit"] - open_trade["entry_price"]) / open_trade["entry_price"] * balance
                    trade_results.append(profit)
                    balance += profit
                    open_trade = None
                elif df["low"][i] <= open_trade["stop_loss"]:
                    loss = (open_trade["stop_loss"] - open_trade["entry_price"]) / open_trade["entry_price"] * balance
                    trade_results.append(loss)
                    balance += loss
                    open_trade = None

            elif open_trade["trade_type"] == "SELL":
                if df["low"][i] <= open_trade["take_profit"]:
                    profit = (open_trade["entry_price"] - open_trade["take_profit"]) / open_trade["entry_price"] * balance
                    trade_results.append(profit)
                    balance += profit
                    open_trade = None
                elif df["high"][i] >= open_trade["stop_loss"]:
                    loss = (open_trade["entry_price"] - open_trade["stop_loss"]) / open_trade["entry_price"] * balance
                    trade_results.append(loss)
                    balance += loss
                    open_trade = None

    total_trades = len(trade_results)
    winning_trades = len([r for r in trade_results if r > 0])
    losing_trades = total_trades - winning_trades
    win_rate = (winning_trades / total_trades) * 100 if total_trades > 0 else 0
    avg_win = np.mean([r for r in trade_results if r > 0]) if winning_trades > 0 else 0
    avg_loss = np.mean([r for r in trade_results if r < 0]) if losing_trades > 0 else 0
    profit_factor = (avg_win * winning_trades) / (-avg_loss * losing_trades) if losing_trades > 0 else 0
    max_drawdown = min(trade_results) if trade_results else 0
    final_balance = balance

    return {
        "Strategy": strategy_name,
        "Total Trades": total_trades,
        "Win Rate (%)": round(win_rate, 2),
        "Profit Factor": round(profit_factor, 2),
        "Max Drawdown (%)": round(max_drawdown / initial_balance * 100, 2),
        "Final Balance ($)": round(final_balance, 2)
    }

# ✅ Async Function to Fetch Data and Run Backtest
async def fetch_and_backtest():
    df_dict = await fetch_all_timeframes(symbol="BTCUSDT", timeframes=["15m", "30m", "1h"], limit=200)

    backtest_results = []
    for interval, df in df_dict.items():
        df["Buy_Signal"], df["Sell_Signal"] = multi_strategy_trading(df)
        results = backtest_strategy(df, strategy_name=f"Backtest - {interval}")
        backtest_results.append(results)

    # 📊 Convert to DataFrame and Display
    df_backtest = pd.DataFrame(backtest_results)
    import ace_tools as tools # type: ignore
    tools.display_dataframe_to_user(name="Backtest Results", dataframe=df_backtest)

# ✅ Run the Backtest
if __name__ == "__main__":
    asyncio.run(fetch_and_backtest())
