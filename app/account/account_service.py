import asyncio
import logging
import threading
import time
import os
from binance import ThreadedWebsocketManager
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from binance.client import Client

# ✅ Use Binance Testnet API for Mock Trading
API_KEY = "a44d949f9e99e9cbb49bfb15d368524454dbe3032d4001fb6c75eb932f5dd001"
API_SECRET = "9be962776fa8625b48fc0188f5643fef0747d6e785908ca059826a424b88eeec"

# ✅ Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ✅ Initialize Binance Client with Testnet
client = Client(API_KEY, API_SECRET, testnet=True)

# ✅ WebSocket-Based Position Tracking
twm = None  # WebSocket instance

# ✅ Account & Risk Management Parameters
MAX_RISK_PER_TRADE = 0.02  # Risk per trade (2% of account balance)
MIN_MARGIN_THRESHOLD = 0.15  # If margin balance < 15% of total balance, reduce positions
RISK_REWARD_RATIO = 2  # 2:1 RR for TP/SL
HEDGE_THRESHOLD = 0.10  # If margin balance is <10%, open hedge trade

# ✅ Store Open Positions
positions = {}

def get_account_balance():
    """Fetch account balance & free margin to prevent liquidation."""
    try:
        account_info = client.futures_account()
        balance_info = next(b for b in account_info["assets"] if b["asset"] == "USDT")
        total_balance = float(balance_info["walletBalance"])
        margin_balance = float(balance_info["marginBalance"])
        unrealized_pnl = float(balance_info["unrealizedProfit"])
        
        return total_balance, margin_balance, unrealized_pnl
    except Exception as e:
        logger.error(f"❌ Error fetching account balance: {e}")
        return 0, 0, 0

def get_open_positions():
    """Fetch currently open positions from Binance Testnet Futures."""
    global positions
    positions.clear()
    try:
        account_info = client.futures_account()
        total_balance, margin_balance, _ = get_account_balance()

        for pos in account_info["positions"]:
            if float(pos["positionAmt"]) != 0:  # Only track open positions
                symbol = pos["symbol"]
                entry_price = float(pos["entryPrice"])
                positionAmt = float(pos["positionAmt"])

                # ✅ Adjust TP & SL dynamically based on account balance
                dynamic_rr = min(RISK_REWARD_RATIO, (margin_balance / total_balance) * 10)  # Scale RR if low balance
                
                if positionAmt > 0:  # Long (BUY)
                    tp_price = entry_price + (entry_price * dynamic_rr / 100)
                    sl_price = entry_price - (entry_price * (dynamic_rr / 2) / 100)
                else:  # Short (SELL)
                    tp_price = entry_price - (entry_price * dynamic_rr / 100)
                    sl_price = entry_price + (entry_price * (dynamic_rr / 2) / 100)

                positions[symbol] = {
                    "positionAmt": positionAmt,
                    "entryPrice": entry_price,
                    "tpPrice": tp_price,
                    "slPrice": sl_price
                }
        
        logger.info(f"📊 Tracked Positions: {positions}")

    except Exception as e:
        logger.error(f"❌ Error fetching positions: {e}")

def close_position(symbol, side, reduce_only=True):
    """Close a position when TP or SL is hit or to reduce risk."""
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=SIDE_SELL if side == SIDE_BUY else SIDE_BUY,  # Close in opposite direction
            type=ORDER_TYPE_MARKET,
            quantity=abs(float(positions[symbol]["positionAmt"])),  # Close full position
            reduceOnly=reduce_only  # Ensure this is a closing trade
        )
        logger.info(f"✅ Closed position for {symbol}: {order}")
    except Exception as e:
        logger.error(f"❌ Error closing position for {symbol}: {e}")

def adjust_position_size():
    """Dynamically adjust position size based on account health."""
    total_balance, margin_balance, _ = get_account_balance()

    if margin_balance / total_balance < MIN_MARGIN_THRESHOLD:
        logger.warning("⚠️ Margin balance is low! Reducing position size...")
        for symbol in positions.keys():
            if abs(positions[symbol]["positionAmt"]) > 0:
                close_position(symbol, positions[symbol]["positionAmt"], reduce_only=True)
                logger.info(f"📉 Reduced position for {symbol} to protect capital.")

def hedge_trade():
    """Open a hedge trade if margin balance is too low to avoid liquidation."""
    total_balance, margin_balance, _ = get_account_balance()
    
    if margin_balance / total_balance < HEDGE_THRESHOLD:
        logger.warning("🚨 Margin is critically low! Opening hedge trade...")
        try:
            order = client.futures_create_order(
                symbol="BTCUSDT",
                side=SIDE_BUY,  # Hedge by opening an opposite trade
                type=ORDER_TYPE_MARKET,
                quantity=0.01  # Small hedge position
            )
            logger.info(f"🛡️ Hedge trade executed: {order}")
        except Exception as e:
            logger.error(f"❌ Error executing hedge trade: {e}")

def handle_message(msg):
    """Handle real-time WebSocket messages."""
    if msg["e"] == "ACCOUNT_UPDATE":
        adjust_position_size()  # Adjust positions if needed
        hedge_trade()  # Open hedge if account is in danger

        positions_update = msg["a"]["P"]
        for position in positions_update:
            symbol = position["s"]
            positionAmt = float(position["pa"])  # Position amount
            entryPrice = float(position["ep"]) if "ep" in position else None

            # ✅ Fetch Latest Market Price
            marketPrice = float(position.get("mp", 0))
            if marketPrice == 0.0:
                ticker = client.futures_mark_price(symbol=symbol)
                marketPrice = float(ticker["markPrice"])
                logger.info(f"🔄 Updated Market Price for {symbol}: {marketPrice}")

            if symbol in positions and entryPrice is not None and positionAmt != 0:
                tp_price = positions[symbol]["tpPrice"]
                sl_price = positions[symbol]["slPrice"]

                logger.info(f"📊 {symbol}: Market Price = {marketPrice}, TP = {tp_price}, SL = {sl_price}")

                # ✅ Check TP & SL Conditions
                if (positionAmt > 0 and marketPrice >= tp_price) or (positionAmt < 0 and marketPrice <= tp_price):
                    logger.info(f"🎯 TAKE PROFIT HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)

                elif (positionAmt > 0 and marketPrice <= sl_price) or (positionAmt < 0 and marketPrice >= sl_price):
                    logger.info(f"⛔ STOP LOSS HIT for {symbol} at {marketPrice}")
                    close_position(symbol, positionAmt)

def start_websocket():
    """Start Binance WebSocket for real-time account updates."""
    global twm
    twm = ThreadedWebsocketManager(API_KEY, API_SECRET, testnet=True)
    twm.start()

    logger.info("🚀 WebSocket started. Listening for account updates...")
    
    twm.start_futures_user_socket(callback=handle_message)  # ✅ Ensure it's tracking futures

# ✅ FIX: Run WebSocket in a separate thread
if __name__ == "__main__":
    get_open_positions()  # Fetch open positions at startup
    
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    # Keep main thread alive
    while True:
        try:
            time.sleep(1)  # ✅ FIX: Use standard sleep to avoid asyncio error
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down WebSocket...")
            twm.stop()
            break
